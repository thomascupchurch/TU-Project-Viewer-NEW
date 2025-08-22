import sys
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QFileDialog, QTreeWidget, QTreeWidgetItem, QLabel, QSplitter, QInputDialog, QDateEdit, QSpinBox
)
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from datetime import datetime, timedelta
from PyQt5.QtCore import Qt, QDate
from PyQt5.QtGui import QPixmap
import fitz  # PyMuPDF


class PDFViewer(QWidget):
    def __init__(self):
        super().__init__()
        self.layout = QVBoxLayout()
        self.setLayout(self.layout)
        self.label = QLabel('No PDF loaded')
        self.label.setAlignment(Qt.AlignCenter)
        self.layout.addWidget(self.label)
        self.nav_layout = QHBoxLayout()
        self.prev_btn = QPushButton('Previous')
        self.next_btn = QPushButton('Next')
        self.page_label = QLabel('')
        self.jump_input = QSpinBox()
        self.jump_input.setMinimum(1)
        self.jump_input.setMaximum(1)
        self.jump_input.setPrefix('Go to: ')
        self.jump_input.setFixedWidth(100)
        self.jump_input.valueChanged.connect(self.jump_to_page)
        self.zoom_in_btn = QPushButton('Zoom +')
        self.zoom_out_btn = QPushButton('Zoom -')
        self.zoom_in_btn.clicked.connect(self.zoom_in)
        self.zoom_out_btn.clicked.connect(self.zoom_out)
        self.prev_btn.clicked.connect(self.prev_page)
        self.next_btn.clicked.connect(self.next_page)
        self.nav_layout.addWidget(self.prev_btn)
        self.nav_layout.addWidget(self.page_label)
        self.nav_layout.addWidget(self.next_btn)
        self.nav_layout.addWidget(self.jump_input)
        self.nav_layout.addWidget(self.zoom_out_btn)
        self.nav_layout.addWidget(self.zoom_in_btn)
        self.layout.addLayout(self.nav_layout)
        self.doc = None
        self.page_num = 0
        self.page_count = 0
        self.zoom = 1.0
        self.update_nav()

    def load_pdf(self, path):
        self.doc = fitz.open(path)
        self.page_count = self.doc.page_count
        self.page_num = 0
        self.zoom = 1.0
        self.jump_input.setMaximum(self.page_count)
        self.jump_input.setValue(1)
        self.show_page()
        self.update_nav()
        self.pdf_path = path

    def show_page(self):
        if self.doc is None or self.page_count == 0:
            self.label.setText('No PDF loaded')
            self.page_label.setText('')
            return
        page = self.doc.load_page(self.page_num)
        pix = page.get_pixmap(matrix=fitz.Matrix(self.zoom, self.zoom))
        img = QPixmap()
        img.loadFromData(pix.tobytes('ppm'))
        self.label.setPixmap(img)
        self.page_label.setText(f'Page {self.page_num+1} / {self.page_count}')
        self.jump_input.blockSignals(True)
        self.jump_input.setValue(self.page_num+1)
        self.jump_input.blockSignals(False)
    def jump_to_page(self, value):
        if self.doc and 1 <= value <= self.page_count:
            self.page_num = value - 1
            self.show_page()
            self.update_nav()

    def zoom_in(self):
        if self.doc:
            self.zoom = min(self.zoom + 0.1, 3.0)
            self.show_page()

    def zoom_out(self):
        if self.doc:
            self.zoom = max(self.zoom - 0.1, 0.2)
            self.show_page()

    def prev_page(self):
        if self.doc and self.page_num > 0:
            self.page_num -= 1
            self.show_page()
            self.update_nav()

    def next_page(self):
        if self.doc and self.page_num < self.page_count - 1:
            self.page_num += 1
            self.show_page()
            self.update_nav()

    def update_nav(self):
        self.prev_btn.setEnabled(self.doc is not None and self.page_num > 0)
        self.next_btn.setEnabled(self.doc is not None and self.page_num < self.page_count - 1)



class GanttChartWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.figure, self.ax = plt.subplots(figsize=(8, 3))
        self.canvas = FigureCanvas(self.figure)
        layout = QVBoxLayout()
        layout.addWidget(self.canvas)
        self.setLayout(layout)
        self.setStyleSheet("background-color: black;")
        self.figure.patch.set_facecolor('black')
        self.ax.set_facecolor('black')
        self.ax.tick_params(colors='white')
        self.ax.xaxis.label.set_color('white')
        self.ax.yaxis.label.set_color('white')
        self.ax.title.set_color('white')
        self.ax.spines['bottom'].set_color('white')
        self.ax.spines['top'].set_color('white')
        self.ax.spines['left'].set_color('white')
        self.ax.spines['right'].set_color('white')
        self.ax.grid(True, color='#444444')
        self.figure.tight_layout()

    def plot_gantt(self, tasks):
        self.ax.clear()
        self.figure.patch.set_facecolor('black')
        self.ax.set_facecolor('black')
        self.ax.tick_params(colors='white')
        self.ax.xaxis.label.set_color('white')
        self.ax.yaxis.label.set_color('white')
        self.ax.title.set_color('white')
        self.ax.spines['bottom'].set_color('white')
        self.ax.spines['top'].set_color('white')
        self.ax.spines['left'].set_color('white')
        self.ax.spines['right'].set_color('white')
        self.ax.grid(True, color='#444444')
        if not tasks:
            self.ax.set_title('Gantt Chart', color='white')
            self.canvas.draw()
            return
        labels = []
        starts = []
        durations = []
        for t in tasks:
            labels.append(t['name'])
            starts.append(mdates.date2num(t['start']))
            durations.append(t['duration'])
        y_pos = range(len(labels))
        self.ax.barh(y_pos, durations, left=starts, color='#FF8200')
        self.ax.set_yticks(y_pos)
        self.ax.set_yticklabels(labels, color='white')
        self.ax.xaxis_date()
        self.ax.set_title('Gantt Chart', color='white')
        self.figure.tight_layout()
        self.canvas.draw()


class ProjectViewer(QMainWindow):
    TASK_COLS = ["Task", "Start Date", "Duration (days)", "PDF Page"]
    def __init__(self):
        super().__init__()
        self.setWindowTitle('TU Project Viewer')
        self.resize(1200, 800)

        splitter = QSplitter()
        self.setCentralWidget(splitter)

        # PDF Viewer
        self.pdf_viewer = PDFViewer()
        left_panel = QWidget()
        left_layout = QVBoxLayout()
        self.load_pdf_btn = QPushButton('Load PDF')
        self.load_pdf_btn.clicked.connect(self.load_pdf)
        left_layout.addWidget(self.load_pdf_btn)
        left_layout.addWidget(self.pdf_viewer)
        self.save_btn = QPushButton('Save Project')
        self.save_btn.clicked.connect(self.save_project)
        self.load_btn = QPushButton('Load Project')
        self.load_btn.clicked.connect(self.load_project)
        left_layout.addWidget(self.save_btn)
        left_layout.addWidget(self.load_btn)
        left_panel.setLayout(left_layout)
        splitter.addWidget(left_panel)

        # Project Plan & Gantt
        right_panel = QWidget()
        right_layout = QVBoxLayout()
        self.task_tree = QTreeWidget()
        self.task_tree.setHeaderLabels(self.TASK_COLS)
        self.task_tree.itemDoubleClicked.connect(self.edit_task)
        self.task_tree.itemClicked.connect(self.on_task_clicked)
        self.task_tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self.task_tree.customContextMenuRequested.connect(self.open_context_menu)
        self.add_task_btn = QPushButton('Add Task')
        self.add_task_btn.clicked.connect(self.add_task)
        right_layout.addWidget(QLabel('Project Plan'))
        right_layout.addWidget(self.task_tree)
        right_layout.addWidget(self.add_task_btn)
        right_layout.addWidget(QLabel('Gantt Chart'))
        self.gantt_chart = GanttChartWidget()
        right_layout.addWidget(self.gantt_chart)
        right_panel.setLayout(right_layout)
        splitter.addWidget(right_panel)

    def open_context_menu(self, position):
        item = self.task_tree.itemAt(position)
        if item is None:
            return
        from PyQt5.QtWidgets import QMenu
        menu = QMenu()
        add_subtask_action = menu.addAction('Add Sub-task')
        action = menu.exec_(self.task_tree.viewport().mapToGlobal(position))
        if action == add_subtask_action:
            self.add_subtask(item)

    def add_subtask(self, parent_item):
        name, ok = QInputDialog.getText(self, 'Add Sub-task', 'Sub-task name:')
        if not (ok and name):
            return
        # Start date
        date_dialog = QDateEdit()
        date_dialog.setCalendarPopup(True)
        date_dialog.setDate(QDate.currentDate())
        date_ok = QInputDialog.getMultiLineText(self, 'Add Sub-task', 'Enter start date (YYYY-MM-DD):', date_dialog.date().toString("yyyy-MM-dd"))
        if date_ok[1] and date_ok[0]:
            start_date = date_ok[0]
        else:
            return
        # Duration
        duration, ok = QInputDialog.getInt(self, 'Add Sub-task', 'Duration (days):', 1, 1, 365)
        if not ok:
            return
        # PDF Page
        pdf_page, ok = QInputDialog.getInt(self, 'Add Sub-task', 'Associated PDF page (leave 0 for none):', 0, 0, 9999)
        if not ok:
            return
        values = [name, start_date, str(duration), str(pdf_page) if pdf_page > 0 else ""]
        item = QTreeWidgetItem(values)
        parent_item.addChild(item)
        parent_item.setExpanded(True)
        self.update_gantt_chart()
        self.add_task_btn = QPushButton('Add Task')
        self.add_task_btn.clicked.connect(self.add_task)
        right_layout.addWidget(QLabel('Project Plan'))
        right_layout.addWidget(self.task_tree)
        right_layout.addWidget(self.add_task_btn)
        right_layout.addWidget(QLabel('Gantt Chart'))
        right_layout.addWidget(GanttChartPlaceholder())
        right_panel.setLayout(right_layout)
        splitter.addWidget(right_panel)

    def load_pdf(self):
        path, _ = QFileDialog.getOpenFileName(self, 'Open PDF', '', 'PDF Files (*.pdf)')
        if path:
            self.pdf_viewer.load_pdf(path)

    def add_task(self):
        name, ok = QInputDialog.getText(self, 'Add Task', 'Task name:')
        if not (ok and name):
            return
        # Start date
        date_dialog = QDateEdit()
        date_dialog.setCalendarPopup(True)
        date_dialog.setDate(QDate.currentDate())
        date_ok = QInputDialog.getMultiLineText(self, 'Add Task', 'Enter start date (YYYY-MM-DD):', date_dialog.date().toString("yyyy-MM-dd"))
        if date_ok[1] and date_ok[0]:
            start_date = date_ok[0]
        else:
            return
        # Duration
        duration, ok = QInputDialog.getInt(self, 'Add Task', 'Duration (days):', 1, 1, 365)
        if not ok:
            return
        # PDF Page
        pdf_page, ok = QInputDialog.getInt(self, 'Add Task', 'Associated PDF page (leave 0 for none):', 0, 0, 9999)
        if not ok:
            return
        selected = self.task_tree.selectedItems()
        values = [name, start_date, str(duration), str(pdf_page) if pdf_page > 0 else ""]
        if selected:
            parent = selected[0]
            item = QTreeWidgetItem(values)
            parent.addChild(item)
            parent.setExpanded(True)
        else:
            item = QTreeWidgetItem(values)
            self.task_tree.addTopLevelItem(item)
        self.update_gantt_chart()

    def edit_task(self, item, column):
        old_name = item.text(0)
        old_date = item.text(1)
        old_duration = item.text(2)
        old_page = item.text(3) if item.columnCount() > 3 else ""
        name, ok = QInputDialog.getText(self, 'Edit Task', 'Task name:', text=old_name)
        if not (ok and name):
            return
        date_ok = QInputDialog.getMultiLineText(self, 'Edit Task', 'Enter start date (YYYY-MM-DD):', old_date)
        if date_ok[1] and date_ok[0]:
            start_date = date_ok[0]
        else:
            return
        duration, ok = QInputDialog.getInt(self, 'Edit Task', 'Duration (days):', int(old_duration) if old_duration.isdigit() else 1, 1, 365)
        if not ok:
            return
        pdf_page, ok = QInputDialog.getInt(self, 'Edit Task', 'Associated PDF page (leave 0 for none):', int(old_page) if old_page.isdigit() else 0, 0, 9999)
        if not ok:
            return
        item.setText(0, name)
        item.setText(1, start_date)
        item.setText(2, str(duration))
        item.setText(3, str(pdf_page) if pdf_page > 0 else "")
        self.update_gantt_chart()
    def on_task_clicked(self, item, column):
        # If the task has an associated PDF page, jump to it
        page_str = item.text(3) if item.columnCount() > 3 else ""
        if page_str and page_str.isdigit():
            page_num = int(page_str)
            if self.pdf_viewer.doc and 1 <= page_num <= self.pdf_viewer.page_count:
                self.pdf_viewer.page_num = page_num - 1
                self.pdf_viewer.show_page()
                self.pdf_viewer.update_nav()

    def update_gantt_chart(self):
        # Gather all tasks and sub-tasks recursively
        def collect_tasks(item, tasks):
            for i in range(item.childCount()):
                collect_tasks(item.child(i), tasks)
            # Only add leaf and parent tasks
            name = item.text(0)
            start = item.text(1)
            duration = item.text(2)
            try:
                start_dt = datetime.strptime(start, "%Y-%m-%d")
                dur = int(duration)
                tasks.append({
                    'name': name,
                    'start': start_dt,
                    'duration': dur
                })
            except Exception:
                pass
        all_tasks = []
        for i in range(self.task_tree.topLevelItemCount()):
            collect_tasks(self.task_tree.topLevelItem(i), all_tasks)
        self.gantt_chart.plot_gantt(all_tasks)

    def save_project(self):
        from PyQt5.QtWidgets import QFileDialog, QMessageBox
        path, _ = QFileDialog.getSaveFileName(self, 'Save Project', '', 'Project Files (*.json)')
        if not path:
            return
        data = {
            'pdf_path': getattr(self.pdf_viewer, 'pdf_path', ''),
            'tasks': self.serialize_tree()
        }
        import json
        try:
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2)
            QMessageBox.information(self, 'Success', 'Project saved successfully!')
        except Exception as e:
            QMessageBox.critical(self, 'Error', f'Failed to save project: {e}')

    def load_project(self):
        from PyQt5.QtWidgets import QFileDialog, QMessageBox
        path, _ = QFileDialog.getOpenFileName(self, 'Load Project', '', 'Project Files (*.json)')
        if not path:
            return
        import json
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
            QMessageBox.information(self, 'Success', 'Project loaded successfully!')
        except Exception as e:
            QMessageBox.critical(self, 'Error', f'Failed to load project: {e}')

    def serialize_tree(self):
        def serialize_item(item):
            d = {
                'values': [item.text(i) for i in range(item.columnCount())],
                'children': [serialize_item(item.child(i)) for i in range(item.childCount())]
            }
            return d
        return [serialize_item(self.task_tree.topLevelItem(i)) for i in range(self.task_tree.topLevelItemCount())]

    def deserialize_tree(self, data, parent):
        from PyQt5.QtWidgets import QTreeWidgetItem
        for entry in data:
            item = QTreeWidgetItem(entry['values'])
            parent.addTopLevelItem(item) if isinstance(parent, QTreeWidget) else parent.addChild(item)
            self.deserialize_tree(entry.get('children', []), item)

    def clear_tree(self):
        self.task_tree.clear()


if __name__ == '__main__':
    app = QApplication(sys.argv)
    viewer = ProjectViewer()
    viewer.show()
    sys.exit(app.exec_())
