from PyQt5.QtWidgets import QStyledItemDelegate, QDateEdit

# Delegate for Start Date column
class DateEditDelegate(QStyledItemDelegate):
    def createEditor(self, parent, option, index):
        editor = QDateEdit(parent)
        editor.setCalendarPopup(True)
        editor.setDisplayFormat('yyyy-MM-dd')
        return editor

    def setEditorData(self, editor, index):
        date_str = index.model().data(index, Qt.EditRole)
        date = QDate.fromString(date_str, 'yyyy-MM-dd')
        if not date.isValid():
            date = QDate.currentDate()
        editor.setDate(date)

    def setModelData(self, editor, model, index):
        model.setData(index, editor.date().toString('yyyy-MM-dd'), Qt.EditRole)

    def updateEditorGeometry(self, editor, option, index):
        editor.setGeometry(option.rect)
import sys
import json
import csv
from datetime import datetime, timedelta

from PyQt5.QtCore import Qt, QDate
from PyQt5.QtGui import QPixmap, QImage
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QFileDialog, QTreeWidget, QTreeWidgetItem, QLabel, QSplitter,
    QInputDialog, QSpinBox, QAbstractItemView, QSizePolicy, QMessageBox
)

import fitz  # PyMuPDF
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas

def _safe_date(s):
    try:
        return datetime.strptime(s, '%Y-%m-%d')
    except Exception:
        return None

class GanttChartWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.figure, self.ax = plt.subplots(figsize=(8, 4))
        self.canvas = FigureCanvas(self.figure)
        layout = QVBoxLayout()
        layout.addWidget(self.canvas)
        self.setLayout(layout)

    def plot_gantt(self, tasks):
        self.ax.clear()
        if not tasks:
            self.ax.text(0.5, 0.5, 'No tasks to display', ha='center', va='center', fontsize=16, color='gray', transform=self.ax.transAxes)
            self.ax.set_xlabel('Date')
            self.ax.xaxis.set_major_locator(mdates.AutoDateLocator())
            self.ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))
            self.figure.autofmt_xdate()
            self.canvas.draw()
            return
        # Debug: print tasks to console
        print('Gantt tasks:', tasks)

        # Ensure all start dates are valid and durations are positive
        valid = True
        for t in tasks:
            if not isinstance(t['start'], datetime) or not isinstance(t['duration'], int) or t['duration'] <= 0:
                valid = False
        if not valid:
            self.ax.text(0.5, 0.5, 'Invalid task data', ha='center', va='center', fontsize=16, color='red', transform=self.ax.transAxes)
            self.ax.set_xlabel('Date')
            self.ax.xaxis.set_major_locator(mdates.AutoDateLocator())
            self.ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))
            self.figure.autofmt_xdate()
            self.canvas.draw()
            return

        # Set x-axis limits to cover all tasks (dates)
        min_start = min(t['start'] for t in tasks)
        max_end = max(t['start'] + timedelta(days=t['duration']) for t in tasks)
        self.ax.set_xlim(mdates.date2num(min_start) - 1, mdates.date2num(max_end) + 1)
        self.ax.set_xlabel('Date')
        self.ax.xaxis_date()  # Explicitly set x-axis as date axis
        self.ax.xaxis.set_major_locator(mdates.AutoDateLocator())
        self.ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))
        self.figure.autofmt_xdate()

        # Set y-ticks and labels to task names
        y_pos = list(range(len(tasks)))
        self.ax.set_yticks(y_pos)
        self.ax.set_yticklabels([t['name'] for t in tasks])
        self.ax.invert_yaxis()  # Gantt: first task at top
        self.figure.tight_layout()
        # Parse depth from name indentation
        def get_depth(name):
            return (len(name) - len(name.lstrip())) // 4
        names = [t['name'] for t in tasks]
        name_to_idx = {name: i for i, name in enumerate(names)}
        starts = [mdates.date2num(t['start']) for t in tasks]
        durations = [t['duration'] for t in tasks]
        y_pos = list(range(len(tasks)))
        # Color by depth: top-level = UT orange, subtasks = lighter orange
        colors = []
        for t in tasks:
            depth = get_depth(t['name'])
            if depth == 0:
                colors.append('#FF8200')
            elif depth == 1:
                colors.append('#FFB366')  # lighter orange
            else:
                colors.append('#FFE0B2')  # even lighter
        try:
            graph = {t['name']: [] for t in tasks}
            for t in tasks:
                dep = t.get('depends_on', '')
                if dep and dep in name_to_idx:
                    graph[dep].append(t['name'])

            # Compute longest path to each node (dynamic programming)
            longest = {}
            pred = {}
            def dfs(node):
                if node in longest:
                    return longest[node]
                idx = name_to_idx[node]
                maxlen = durations[idx]
                maxpred = None
                # Find all predecessors (tasks that this node depends on)
                for prev in [t['name'] for t in tasks if node == t.get('depends_on', '')]:
                    plen = dfs(prev) + durations[idx]
                    if plen > maxlen:
                        maxlen = plen
                        maxpred = prev
                longest[node] = maxlen
                pred[node] = maxpred
                return maxlen
            for n in names:
                dfs(n)
            if longest:
                end_node = max(names, key=lambda n: longest[n])
                n = end_node
                while n is not None:
                    critical_path.add(n)
                    n = pred[n]
        except Exception as e:
            # If any error, just don't highlight critical path
            critical_path = set()

        # Debug: print bar data
        print('starts:', starts)
        print('durations:', durations)
        print('colors:', colors)
        print('names:', names)
        print('y_pos:', y_pos)
        # Draw bars, highlight critical path if available
        cp_indices = []
        for i in range(len(names)):
            start = starts[i]
            dur = durations[i]
            color = colors[i]
            name = names[i]
            try:
                if name in critical_path:
                    self.ax.barh(i, dur, left=start, height=0.4, align='center', color=color, edgecolor='red', linewidth=3, zorder=3)
                    cp_indices.append(i)
                else:
                    self.ax.barh(i, dur, left=start, height=0.4, align='center', color=color, edgecolor='black', zorder=2)
            except Exception as e:
                print(f'Bar plot error for {name}:', e)
                # Fallback: plot without critical path
                self.ax.barh(i, dur, left=start, height=0.4, align='center', color=color, edgecolor='black', zorder=2)
        # Draw a red line connecting the centers of the bars on the critical path
        if len(cp_indices) > 1:
            cp_x = []
            cp_y = []
            for idx in cp_indices:
                # Center of the bar: start + dur/2, y = idx
                cp_x.append(starts[idx] + durations[idx]/2)
                cp_y.append(idx)
            self.ax.plot(cp_x, cp_y, color='red', linewidth=2.5, marker='o', zorder=4, label='Critical Path')
        self.ax.set_yticks(y_pos)
        self.ax.set_yticklabels(names)
        self.ax.set_xlabel('Date')
        self.ax.xaxis.set_major_locator(mdates.AutoDateLocator())
        self.ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))
        self.figure.autofmt_xdate()
        # Draw dependency arrows as before
        for i, t in enumerate(tasks):
            dep = t.get('depends_on', '')
            if dep and dep in name_to_idx:
                dep_idx = name_to_idx[dep]
                dep_task = tasks[dep_idx]
                dep_end = mdates.date2num(dep_task['start'] + timedelta(days=dep_task['duration']))
                self.ax.annotate('', xy=(starts[i], i), xytext=(dep_end, dep_idx), arrowprops=dict(arrowstyle='->', color='red', lw=1.2))
        # Draw vertical lines from parent to subtasks
        parent_stack = []  # (y, depth, x)
        for i, t in enumerate(tasks):
            depth = get_depth(t['name'])
            # Remove stack entries deeper or at same level
            while parent_stack and parent_stack[-1][1] >= depth:
                parent_stack.pop()
            if parent_stack:
                parent_y, parent_depth, parent_x = parent_stack[-1]
                self.ax.plot([parent_x, starts[i]], [parent_y, i], color='#888', linestyle='--', linewidth=1)
            parent_stack.append((i, depth, starts[i]))
        self.canvas.draw()
    def export_chart(self, parent):
        path, _ = QFileDialog.getSaveFileName(parent, 'Export Gantt Chart', '', 'PNG Files (*.png);;PDF Files (*.pdf)')
        if not path:
            return
        try:
            self.figure.savefig(path, bbox_inches='tight')
        except Exception as e:
            QMessageBox.critical(parent, 'Error', f'Failed to export chart: {e}')

class PDFLabel(QLabel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._pdf_viewer = parent

    def resizeEvent(self, event):
        super().resizeEvent(event)
        # Call parent's show_page to re-render PDF at new size
        if self._pdf_viewer and hasattr(self._pdf_viewer, 'show_page'):
            self._pdf_viewer.show_page()


class PDFViewer(QWidget):
    def __init__(self):
        super().__init__()
        self.layout = QVBoxLayout()
        self.setLayout(self.layout)
        self.file_label = QLabel('No PDF loaded')
        self.file_label.setAlignment(Qt.AlignCenter)
        self.layout.addWidget(self.file_label)
        self.label = PDFLabel(self)
        self.label.setText('No PDF loaded')
        self.label.setAlignment(Qt.AlignCenter)
        self.label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.label.setScaledContents(False)
        self.label.setMinimumHeight(400)
        self.layout.addWidget(self.label, stretch=1)
        self.nav_layout = QHBoxLayout()
        self.prev_btn = QPushButton('Previous')
        self.prev_btn.clicked.connect(self.prev_page)
        self.next_btn = QPushButton('Next')
        self.next_btn.clicked.connect(self.next_page)
        self.page_label = QLabel('')
        self.jump_input = QSpinBox()
        self.jump_input.setMinimum(1)
        self.jump_input.setMaximum(1)
        self.jump_input.setFixedWidth(100)
        self.jump_input.valueChanged.connect(self.jump_to_page)
        self.nav_layout.addWidget(self.prev_btn)
        self.nav_layout.addWidget(self.next_btn)
        self.nav_layout.addStretch(1)
        self.nav_layout.addWidget(self.page_label)
        self.nav_layout.addWidget(self.jump_input)
        self.layout.addLayout(self.nav_layout)
        self.layout.setStretch(0, 0)  # File label does not expand
        self.layout.setStretch(1, 1)  # PDF label takes all available space
        self.layout.setStretch(2, 0)  # Navigation bar does not expand

        self.doc = None
        self.page_count = 0
        self.page_num = 0
        self.pdf_path = ''

    def load_pdf(self, path):
        import os
        try:
            self.doc = fitz.open(path)
            self.page_count = self.doc.page_count
            self.page_num = 0
            self.pdf_path = path
            self.file_label.setText(os.path.basename(path))
            self.show_page()
            self.update_nav()
        except Exception as e:
            self.label.setText(f"Failed to load PDF: {e}")
            self.file_label.setText('No PDF loaded')

    def show_page(self):
        if not self.doc:
            return
        from PyQt5.QtCore import QTimer
        def render():
            try:
                page = self.doc.load_page(self.page_num)
                label_width = max(self.label.width(), 1)
                label_height = max(self.label.height(), 1)
                # Render at a high DPI (200), then scale pixmap to label size
                zoom = 200 / 72  # 200 DPI
                matrix = fitz.Matrix(zoom, zoom)
                pix = page.get_pixmap(matrix=matrix)
                fmt = QImage.Format_RGBA8888 if pix.alpha else QImage.Format_RGB888
                img = QImage(pix.samples, pix.width, pix.height, pix.stride, fmt)
                pixmap = QPixmap.fromImage(img)
                # Use the original PDF page's aspect ratio for scaling
                page_rect = page.rect
                page_aspect = page_rect.width / page_rect.height if page_rect.height else 1
                label_width = max(self.label.width(), 1)
                label_height = max(self.label.height(), 1)
                # Always scale pixmap to fit label, preserving aspect ratio
                scaled_pixmap = pixmap.scaled(label_width, label_height, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                self.label.setPixmap(scaled_pixmap)
            except Exception as e:
                self.label.setText(f"Failed to render page: {e}")
        QTimer.singleShot(0, render)
    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.show_page()

    def update_nav(self):
        if not self.doc:
            self.page_label.setText('')
            self.jump_input.setMaximum(1)
            return
        self.page_label.setText(f"Page {self.page_num+1} / {self.page_count}")
        self.jump_input.blockSignals(True)
        self.jump_input.setMaximum(self.page_count)
        self.jump_input.setValue(self.page_num+1)
        self.jump_input.blockSignals(False)

    def jump_to_page(self, value=None):
        try:
            if value is None:
                value = self.jump_input.value()
            v = int(value)
        except Exception:
            return
        if self.page_count:
            v = max(1, min(self.page_count, v))
        self.page_num = max(0, v-1)
        self.show_page()
        self.update_nav()

    def prev_page(self):
        if not self.doc:
            return
        if self.page_num > 0:
            self.page_num -= 1
            self.show_page()
            self.update_nav()

    def next_page(self):
        if not self.doc:
            return
        if self.page_num < self.page_count - 1:
            self.page_num += 1
            self.show_page()
            self.update_nav()

class ProjectViewer(QMainWindow):
    def load_pdf(self):
        path, _ = QFileDialog.getOpenFileName(self, 'Open PDF', '', 'PDF Files (*.pdf)')
        if path:
            self.pdf_viewer.load_pdf(path)
            self.pdf_viewer.pdf_path = path
            self.project_file_label.setText(f'PDF: {path.split('/')[-1]}')
    def __init__(self):
        super().__init__()
        import os
        self.CONFIG_PATH = os.path.join(os.path.dirname(__file__), 'last_project_path.txt')
        self.setup_ui()
    TASK_COLS = ['Task', 'Start Date', 'Duration (days)', 'PDF Page', 'Depends On', 'Resources', 'Notes']
    def get_all_resources(self):
        resources = set()
        def collect(item):
            if item.text(5):
                resources.add(item.text(5))
            for i in range(item.childCount()):
                collect(item.child(i))
        for i in range(self.task_tree.topLevelItemCount()):
            collect(self.task_tree.topLevelItem(i))
        return sorted(r for r in resources if r)
    # ...existing code...
    def eventFilter(self, obj, event):
        from PyQt5.QtCore import QEvent
        from PyQt5.QtWidgets import QDateEdit
        if obj == self.task_tree and event.type() == QEvent.ChildAdded:
            editor = event.child()
            if hasattr(editor, 'setCalendarPopup') and hasattr(editor, 'setDisplayFormat'):
                editor.setCalendarPopup(True)
                editor.setDisplayFormat('yyyy-MM-dd')
        return super().eventFilter(obj, event)

    def edit_start_date(self, item, column):
        from PyQt5.QtWidgets import QDateEdit
        if column == 1:  # Start Date column
            date_str = item.text(1)
            from PyQt5.QtCore import QDate
            try:
                date = QDate.fromString(date_str, 'yyyy-MM-dd')
                if not date.isValid():
                    date = QDate.currentDate()
            except Exception:
                date = QDate.currentDate()
            date_edit = QDateEdit(date, self.task_tree)

    def setup_ui(self):
        # Main layout for the window
        main_widget = QWidget()
        main_layout = QVBoxLayout()
        main_widget.setLayout(main_layout)
        # Project file label at the top
        self.project_file_label = QLabel('No project loaded')
        self.project_file_label.setMinimumHeight(24)
        main_layout.addWidget(self.project_file_label)
        # Splitter for left/right panels
        self.splitter = QSplitter()
        # --- Left panel (PDF viewer) ---
        left_panel = QWidget()
        left_layout = QVBoxLayout()
        left_panel.setLayout(left_layout)
        left_panel.setMinimumWidth(420)
        self.pdf_viewer = PDFViewer()
        self.pdf_viewer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        left_layout.addWidget(self.pdf_viewer)
        self.load_pdf_btn = QPushButton('Load PDF')
        self.load_pdf_btn.clicked.connect(self.load_pdf)
        left_layout.addWidget(self.load_pdf_btn)
        self.splitter.addWidget(left_panel)

        # --- Right panel (Task tree and Gantt chart) ---
        right_panel = QWidget()
        right_layout = QVBoxLayout()
        right_panel.setLayout(right_layout)
        # --- Task-related buttons ---
        btn_layout = QHBoxLayout()
        self.add_task_btn = QPushButton('Add Task')
        self.add_task_btn.clicked.connect(self.add_task)
        btn_layout.addWidget(self.add_task_btn)
        self.remove_task_btn = QPushButton('Remove Task')
        self.remove_task_btn.clicked.connect(self.remove_task)
        btn_layout.addWidget(self.remove_task_btn)
        self.export_csv_btn = QPushButton('Export CSV')
        self.export_csv_btn.clicked.connect(self.export_project_csv)
        btn_layout.addWidget(self.export_csv_btn)
        self.save_project_btn = QPushButton('Save Project')
        self.save_project_btn.clicked.connect(self.save_project)
        btn_layout.addWidget(self.save_project_btn)

        self.load_project_btn = QPushButton('Load Project')
        self.load_project_btn.clicked.connect(self.load_project)
        btn_layout.addWidget(self.load_project_btn)
        self.export_gantt_btn = QPushButton('Export Gantt Chart')
        self.export_gantt_btn.clicked.connect(lambda: self.gantt_chart.export_chart(self))
        btn_layout.addWidget(self.export_gantt_btn)

        # Add Deselect Task button
        self.deselect_task_btn = QPushButton('Deselect Task')
        self.deselect_task_btn.setToolTip('Clear selection so new tasks are top-level')
        self.deselect_task_btn.clicked.connect(self.deselect_task)
        btn_layout.addWidget(self.deselect_task_btn)

        btn_layout.addStretch(1)
        right_layout.addLayout(btn_layout)

        self.task_tree = QTreeWidget()
        self.task_tree.setHeaderLabels(self.TASK_COLS)
        right_layout.addWidget(self.task_tree)

        self.gantt_chart = GanttChartWidget()
        right_layout.addWidget(self.gantt_chart)
        self.splitter.addWidget(right_panel)

        # Restore jump-to-page feature: connect itemClicked to on_task_clicked
        self.task_tree.itemClicked.connect(self.on_task_clicked)

        # Set initial splitter sizes for a balanced look
        self.splitter.setSizes([500, 700])
        # Ensure splitter expands to fill available space
        self.splitter.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        main_layout.addWidget(self.splitter, stretch=1)
        main_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setCentralWidget(main_widget)
        self.resize(1200, 800)

    def deselect_task(self):
        self.task_tree.clearSelection()

    def remove_task(self):
        sel = self.task_tree.selectedItems()
        if not sel:
            return
        for item in sel:
            (item.parent() or self.task_tree.invisibleRootItem()).removeChild(item)
        self.update_gantt_chart()

    def add_task(self):
        name, ok = QInputDialog.getText(self, 'Add Task', 'Task name:')
        if not (ok and name):
            return

        # Use QDateEdit in a dialog for date selection
        from PyQt5.QtWidgets import QDialog, QDialogButtonBox, QFormLayout, QDateEdit
        date_dialog = QDialog(self)
        date_dialog.setWindowTitle('Select Start Date')
        form = QFormLayout(date_dialog)
        date_edit = QDateEdit(QDate.currentDate())
        date_edit.setCalendarPopup(True)
        form.addRow('Start date:', date_edit)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        form.addWidget(buttons)
        buttons.accepted.connect(date_dialog.accept)
        buttons.rejected.connect(date_dialog.reject)
        if date_dialog.exec_() != QDialog.Accepted:
            return
        date_str = date_edit.date().toString('yyyy-MM-dd')

        duration, ok = QInputDialog.getInt(self, 'Add Task', 'Duration (days):', 1, 1, 365)
        if not ok:
            return
        pdf_page, ok = QInputDialog.getInt(self, 'Add Task', 'Associated PDF page (0 for none):', 0, 0, 9999)
        if not ok:
            return
        dep = ''
        names = self.get_all_task_names()
        if names:
            dep_item, ok = QInputDialog.getItem(self, 'Depends On', 'Depends on (optional):', ['None'] + names, 0, False)
            if ok and dep_item and dep_item != 'None':
                dep = dep_item
        resources, ok = QInputDialog.getText(self, 'Add Task', 'Resources (optional):')
        if not ok:
            resources = ''
        notes, ok = QInputDialog.getText(self, 'Add Task', 'Notes (optional):')
        if not ok:
            notes = ''
        vals = [name, date_str, str(duration), str(pdf_page) if pdf_page>0 else '', dep, resources, notes]
        sel = self.task_tree.selectedItems()
        item = QTreeWidgetItem(vals)
        for i in range(len(vals)):
            item.setFlags(item.flags() | Qt.ItemIsEditable)
        if sel:
            sel[0].addChild(item)
        else:
            self.task_tree.addTopLevelItem(item)
        self.update_gantt_chart()

    def on_item_changed(self, item, column):
        self.update_gantt_chart()

    def on_task_clicked(self, item, column):
        page_str = item.text(3) if item.columnCount() > 3 else ''
        if page_str and page_str.isdigit():
            p = int(page_str)
            if hasattr(self.pdf_viewer, 'doc') and self.pdf_viewer.doc and 1 <= p <= self.pdf_viewer.page_count:
                self.pdf_viewer.page_num = p-1
                self.pdf_viewer.show_page()
                self.pdf_viewer.update_nav()

    def get_all_task_names(self):
        names = []
        def collect(item):
            names.append(item.text(0))
            for i in range(item.childCount()):
                collect(item.child(i))
        for i in range(self.task_tree.topLevelItemCount()):
            collect(self.task_tree.topLevelItem(i))
        return names

    def update_gantt_chart(self):
        def collect(item, tasks, depth=0):
            name = item.text(0)
            start = item.text(1)
            dur = item.text(2)
            dep = item.text(4) if item.columnCount() > 4 else ''
            resources = item.text(5) if item.columnCount() > 5 else ''
            notes = item.text(6) if item.columnCount() > 6 else ''
            sd = _safe_date(start)
            try:
                d = int(dur)
            except Exception:
                d = None
            if sd and d:
                # Indent name by depth for Gantt chart
                tasks.append({'name': ('    ' * depth) + name, 'start': sd, 'duration': d, 'depends_on': dep, 'resources': resources, 'notes': notes})
            for i in range(item.childCount()):
                collect(item.child(i), tasks, depth+1)
            print('setup_ui: end')
        all_tasks = []
        for i in range(self.task_tree.topLevelItemCount()):
            collect(self.task_tree.topLevelItem(i), all_tasks, 0)
        name_to_task = {t['name']: t for t in all_tasks}
        changed = True
        while changed:
            changed = False
            for t in all_tasks:
                dep = t.get('depends_on', '')
                if dep and dep in name_to_task:
                    dep_task = name_to_task[dep]
                    dep_end = dep_task['start'] + timedelta(days=dep_task['duration'])
                    if t['start'] < dep_end:
                        t['start'] = dep_end
                        changed = True
        self.gantt_chart.plot_gantt(all_tasks)

    def serialize_tree(self):
        def ser(item):
            return {'values': [item.text(i) for i in range(item.columnCount())], 'children': [ser(item.child(i)) for i in range(item.childCount())]}
        return [ser(self.task_tree.topLevelItem(i)) for i in range(self.task_tree.topLevelItemCount())]

    def deserialize_tree(self, data, parent):
        for entry in data:
            vals = entry.get('values', [])
            if len(vals) < len(self.TASK_COLS):
                vals += [''] * (len(self.TASK_COLS)-len(vals))
            item = QTreeWidgetItem(vals)
            for i in range(len(vals)):
                item.setFlags(item.flags() | Qt.ItemIsEditable)
            if isinstance(parent, QTreeWidget):
                parent.addTopLevelItem(item)
            else:
                parent.addChild(item)
            self.deserialize_tree(entry.get('children', []), item)

    def clear_tree(self):
        self.task_tree.clear()

    def save_last_project_path(self, path):
        try:
            with open(self.CONFIG_PATH, 'w', encoding='utf-8') as f:
                f.write(path)
        except Exception as e:
            QMessageBox.critical(self, 'Error', f'Failed to save project: {e}')


    def load_last_project_path(self):
        try:
            with open(self.CONFIG_PATH, 'r', encoding='utf-8') as f:
                return f.read().strip()
        except Exception:
            return None

    def save_project(self):
        import os
        path, _ = QFileDialog.getSaveFileName(self, 'Save Project', '', 'Project Files (*.json)')
        if not path:
            return
        data = {'pdf_path': getattr(self.pdf_viewer, 'pdf_path', ''), 'tasks': self.serialize_tree()}
        try:
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2)
            self.project_file_label.setText(f'Project File: {os.path.basename(path)}')
        except Exception as e:
            QMessageBox.critical(self, 'Error', f'Failed to save project: {e}')

    def load_project(self, path=None):
        import os
        if not path:
            path, _ = QFileDialog.getOpenFileName(self, 'Load Project', '', 'Project Files (*.json)')
        if not path:
            return
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            self.clear_tree()
            pdf_path = data.get('pdf_path', '')
            if pdf_path:
                self.pdf_viewer.load_pdf(pdf_path)
                self.pdf_viewer.pdf_path = pdf_path
            self.deserialize_tree(data.get('tasks', []), self.task_tree)
            self.update_gantt_chart()
            self.save_last_project_path(path)
            self.project_file_label.setText(f'Project File: {os.path.basename(path)}')
        except Exception as e:
            QMessageBox.critical(self, 'Error', f'Failed to load project: {e}')

    def export_project_csv(self):
        path, _ = QFileDialog.getSaveFileName(self, 'Export Project as CSV', '', 'CSV File (*.csv)')
        if not path:
            return
        rows = []
        def collect_rows(item, parent_name=''):
            rows.append({
                'Task': item.text(0),
                'Start Date': item.text(1),
                'Duration (days)': item.text(2),
                'PDF Page': item.text(3) if item.columnCount()>3 else '',
                'Depends On': item.text(4) if item.columnCount()>4 else '',
                'Resources': item.text(5) if item.columnCount()>5 else '',
                'Notes': item.text(6) if item.columnCount()>6 else '',
                'Parent Task': parent_name
            })
            for i in range(item.childCount()):
                collect_rows(item.child(i), parent_name=item.text(0))
        for i in range(self.task_tree.topLevelItemCount()):
            collect_rows(self.task_tree.topLevelItem(i))
        fieldnames = ['Task','Start Date','Duration (days)','PDF Page','Depends On','Resources','Notes','Parent Task']
        try:
            with open(path, 'w', newline='', encoding='utf-8') as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                writer.writeheader()
                for r in rows:
                    writer.writerow(r)
        except Exception as e:
            QMessageBox.critical(self, 'Error', f'Failed to export CSV: {e}')

if __name__ == '__main__':
    print('MAIN BLOCK EXECUTED')
    import traceback
    print('Before QApplication')
    app = QApplication(sys.argv)
    print('After QApplication')
    try:
        print('Before ProjectViewer')
        viewer = ProjectViewer()
        print('After ProjectViewer')
        viewer.show()
        print('After viewer.show()')
        last = viewer.load_last_project_path()
        print('After load_last_project_path')
        if last:
            print('Before load_project')
            viewer.load_project(last)
            print('After load_project')
        print('Before app.exec_()')
        sys.exit(app.exec_())
    except Exception:
        print('Exception during startup:')
        traceback.print_exc()
        sys.exit(1)
