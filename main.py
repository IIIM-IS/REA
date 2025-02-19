# -----------------------------------------------------------------------------
# Authors: Arash Sheikhlar and Kristinn Thorisson
# Project: Research Expenditure Allocation (REA)
# -----------------------------------------------------------------------------
# Copyright (c) 2025, Arash Sheikhlar and Kristinn Thorisson. All rights reserved.
#
# This software is provided "as is", without warranty of any kind, express or
# implied, including but not limited to the warranties of merchantability,
# fitness for a particular purpose, and noninfringement. In no event shall
# the authors be liable for any claim, damages, or other liability, whether
# in an action of contract, tort, or otherwise, arising from, out of, or in
# connection with the software or the use or other dealings in the software.
#
# Unauthorized copying, distribution, or modification of this code, via any
# medium, is strictly prohibited unless prior written permission is obtained
# from the authors.
# -----------------------------------------------------------------------------

from PyQt5.QtCore import QCoreApplication
from PyQt5.QtWidgets import QApplication
import sys
from Model import ReaDataModel
from View import ReaDataView
from Control import Controller

def main():
    QCoreApplication.setOrganizationName("IIIM")
    QCoreApplication.setApplicationName("REAApp")
    
    app = QApplication(sys.argv)
    model = ReaDataModel()
    view = ReaDataView()
    controller = Controller(model, view)
    view.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()