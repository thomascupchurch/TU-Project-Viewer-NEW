import sys
from PyQt5.QtWidgets import QApplication, QLabel

app = QApplication(sys.argv)
label = QLabel('PyQt5 Test - If you see this, PyQt5 is working!')
label.setStyleSheet('background: green; color: white; font-size: 32px;')
label.setMinimumSize(600, 200)
label.setAlignment(Qt.AlignCenter)
label.show()
sys.exit(app.exec_())
