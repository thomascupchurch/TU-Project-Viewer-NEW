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
            self.canvas.draw()
            return
        tasks_sorted = sorted(tasks, key=lambda t: t['start'])
        names = [t['name'] for t in tasks_sorted]
        starts = [mdates.date2num(t['start']) for t in tasks_sorted]
        durations = [t['duration'] for t in tasks_sorted]
        y_pos = list(range(len(tasks_sorted)))
        # Official University of Tennessee orange: #FF8200
        self.ax.barh(y_pos, durations, left=starts, height=0.4, align='center', color='#FF8200', edgecolor='black')
        self.ax.set_yticks(y_pos)
        self.ax.set_yticklabels(names)
        self.ax.set_xlabel('Date')
        self.ax.xaxis.set_major_locator(mdates.AutoDateLocator())
        self.ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))
        self.figure.autofmt_xdate()
        name_to_idx = {t['name']: i for i, t in enumerate(tasks_sorted)}
        for i, t in enumerate(tasks_sorted):
            dep = t.get('depends_on', '')
            if dep and dep in name_to_idx:
                dep_idx = name_to_idx[dep]
                dep_task = tasks_sorted[dep_idx]
                dep_end = mdates.date2num(dep_task['start'] + timedelta(days=dep_task['duration']))
                self.ax.annotate('', xy=(starts[i], i), xytext=(dep_end, dep_idx), arrowprops=dict(arrowstyle='->', color='red', lw=1.2))
        self.ax.grid(True, axis='x', linestyle='--', alpha=0.6)
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
        self.layout.setStretch(0, 1)  # Make the label take all available space
        self.layout.setStretch(1, 0)  # Navigation bar does not expand

        self.doc = None
        self.page_count = 0
        self.page_num = 0
        self.pdf_path = ''

    def load_pdf(self, path):
        try:
            self.doc = fitz.open(path)
            self.page_count = self.doc.page_count
            self.page_num = 0
            self.pdf_path = path
            self.show_page()
            self.update_nav()
        except Exception as e:
            self.label.setText(f"Failed to load PDF: {e}")

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
    TASK_COLS = ['Task', 'Start Date', 'Duration (days)', 'PDF Page', 'Depends On']
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
        self.splitter = QSplitter()
        left_panel = QWidget()
        left_layout = QVBoxLayout()
        left_panel.setLayout(left_layout)
        left_panel.setMinimumWidth(420)
        pdf_label = QLabel('PDF Viewer')
        pdf_label.setStyleSheet('font-weight: bold; font-size: 14px; margin-bottom: 4px;')
        left_layout.addWidget(pdf_label)
        self.pdf_viewer = PDFViewer()
        self.pdf_viewer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        left_layout.addWidget(self.pdf_viewer)
        self.load_pdf_btn = QPushButton('Load PDF')
        self.load_pdf_btn.clicked.connect(self.load_pdf)
        left_layout.addWidget(self.load_pdf_btn)
        controls_section = QHBoxLayout()
        self.save_btn = QPushButton('💾 Save Project')
        self.save_btn.clicked.connect(self.save_project)
        self.load_btn = QPushButton('📂 Load Project')
        self.load_btn.clicked.connect(self.load_project)
        controls_section.addWidget(self.save_btn)
        controls_section.addWidget(self.load_btn)
        left_layout.addLayout(controls_section)
        left_layout.addStretch(1)
        self.splitter.addWidget(left_panel)

        right_panel = QWidget()
        right_layout = QVBoxLayout()
        right_panel.setLayout(right_layout)
        right_panel.setMinimumWidth(600)
        plan_label = QLabel('Project Plan')
        plan_label.setStyleSheet('font-weight: bold; font-size: 14px; margin-bottom: 4px;')
        right_layout.addWidget(plan_label)
        self.task_tree = QTreeWidget()
        self.task_tree.setHeaderLabels(self.TASK_COLS)
        self.task_tree.setEditTriggers(QAbstractItemView.DoubleClicked | QAbstractItemView.SelectedClicked | QAbstractItemView.EditKeyPressed)
        self.task_tree.itemChanged.connect(self.on_item_changed)
        self.task_tree.itemClicked.connect(self.on_task_clicked)
        self.task_tree.setItemDelegateForColumn(1, DateEditDelegate())
        right_layout.addWidget(self.task_tree)
        btn_row = QHBoxLayout()
        self.add_task_btn = QPushButton('➕ Add Task')
        self.add_task_btn.clicked.connect(self.add_task)
        btn_row.addWidget(self.add_task_btn)
        self.delete_task_btn = QPushButton('🗑️ Delete Task')
        self.delete_task_btn.clicked.connect(self.delete_task)
        btn_row.addWidget(self.delete_task_btn)
        btn_row.addStretch(1)
        right_layout.addLayout(btn_row)
        gantt_label = QLabel('Gantt Chart')
        right_layout.addWidget(gantt_label)
        self.gantt_chart = GanttChartWidget()
        right_layout.addWidget(self.gantt_chart)
        export_section = QHBoxLayout()
        self.export_gantt_btn = QPushButton('Export Gantt Chart')
        self.export_gantt_btn.clicked.connect(lambda: self.gantt_chart.export_chart(self))
        self.export_csv_btn = QPushButton('Export Project as CSV')
        self.export_csv_btn.clicked.connect(self.export_project_csv)
        export_section.addWidget(self.export_gantt_btn)
        export_section.addWidget(self.export_csv_btn)
        right_layout.addLayout(export_section)
        right_layout.addStretch(1)
        self.splitter.addWidget(right_panel)
        try:
            self.splitter.setStretchFactor(0, 3)
            self.splitter.setStretchFactor(1, 2)
        except Exception:
            pass
        # Now create a vertical layout for the label and splitter
        container = QWidget()
        container.setMinimumSize(900, 600)
        vlayout = QVBoxLayout()
        vlayout.setContentsMargins(0, 0, 0, 0)
        vlayout.addWidget(self.project_file_label)
        vlayout.addWidget(self.splitter)
        container.setLayout(vlayout)
        self.setCentralWidget(container)
    def __init__(self):
        super().__init__()
        self.project_file_label = QLabel('')
        self.setup_ui()

    def delete_task(self):
        sel = self.task_tree.selectedItems()
        if not sel:
            return
        item = sel[0]
        parent = item.parent()
        if parent is None:
            idx = self.task_tree.indexOfTopLevelItem(item)
            self.task_tree.takeTopLevelItem(idx)
        else:
            parent.removeChild(item)
        self.update_gantt_chart()

    def load_pdf(self):
        path, _ = QFileDialog.getOpenFileName(self, 'Load PDF', '', 'PDF Files (*.pdf)')
        if path:
            self.pdf_viewer.load_pdf(path)

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
        vals = [name, date_str, str(duration), str(pdf_page) if pdf_page>0 else '', dep]
        sel = self.task_tree.selectedItems()
        item = QTreeWidgetItem(vals)
        for i in range(len(vals)):
            item.setFlags(item.flags() | Qt.ItemIsEditable)
        if sel and sel[0].parent() is None:
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
        def collect(item, tasks):
            for i in range(item.childCount()):
                collect(item.child(i), tasks)
                # Create the splitter and panels as before
                self.splitter = QSplitter()
                # ...existing code for left_panel and right_panel setup...
                # Place everything in a vertical layout with the project file label at the top
                container = QWidget()
                vlayout = QVBoxLayout()
                vlayout.setContentsMargins(0, 0, 0, 0)
                vlayout.addWidget(self.project_file_label)
                vlayout.addWidget(self.splitter)
                container.setLayout(vlayout)
                self.setCentralWidget(container)
            name = item.text(0)
            start = item.text(1)
            dur = item.text(2)
            dep = item.text(4) if item.columnCount() > 4 else ''
            sd = _safe_date(start)
            try:
                d = int(dur)
            except Exception:
                d = None
            if sd and d:
                tasks.append({'name': name, 'start': sd, 'duration': d, 'depends_on': dep})
        all_tasks = []
        for i in range(self.task_tree.topLevelItemCount()):
            collect(self.task_tree.topLevelItem(i), all_tasks)
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
        path, _ = QFileDialog.getSaveFileName(self, 'Save Project', '', 'Project Files (*.json)')
        if not path:
            return
        data = {'pdf_path': getattr(self.pdf_viewer, 'pdf_path', ''), 'tasks': self.serialize_tree()}
        try:
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            QMessageBox.critical(self, 'Error', f'Failed to save project: {e}')

    def load_project(self, path=None):
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
        except Exception as e:
            QMessageBox.critical(self, 'Error', f'Failed to load project: {e}')

    def export_project_csv(self):
        path, _ = QFileDialog.getSaveFileName(self, 'Export Project as CSV', '', 'CSV File (*.csv)')
        if not path:
            return
        rows = []
        def collect_rows(item, parent_name=''):
            rows.append({'Task': item.text(0), 'Start Date': item.text(1), 'Duration (days)': item.text(2), 'PDF Page': item.text(3) if item.columnCount()>3 else '', 'Depends On': item.text(4) if item.columnCount()>4 else '', 'Parent Task': parent_name})
            for i in range(item.childCount()):
                collect_rows(item.child(i), parent_name=item.text(0))
        for i in range(self.task_tree.topLevelItemCount()):
            collect_rows(self.task_tree.topLevelItem(i))
        fieldnames = ['Task','Start Date','Duration (days)','PDF Page','Depends On','Parent Task']
        try:
            with open(path, 'w', newline='', encoding='utf-8') as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                writer.writeheader()
                for r in rows:
                    writer.writerow(r)
        except Exception as e:
            QMessageBox.critical(self, 'Error', f'Failed to export CSV: {e}')

if __name__ == '__main__':
    app = QApplication(sys.argv)
    viewer = ProjectViewer()
    viewer.show()
    last = viewer.load_last_project_path()
    if last:
        viewer.load_project(last)
    sys.exit(app.exec_())
