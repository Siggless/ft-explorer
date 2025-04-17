from typing import List
from PyQt5.QtWidgets import *
from PyQt5.QtGui import *
from PyQt5.QtCore import *

from .bpd_classes import *
from .bpd_gui import *
from .model_variable import *

"""
Variable List Views
"""
class VarsNode(GraphNode):
    def __init__(self, seqID, parent):
        super().__init__("Variables", seqID, parent)
        self.sequence: BehaviorSequence = self.graph.sequence
        self.model: VariableItemModel = self.sequence.varModel
        
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        layout = QGridLayout(self)
        layout.addWidget(QLabel("Name"),0,0)
        layout.addWidget(QLabel("Type"),0,1)
        helpButton = QPushButton("?")
        helpButton.clicked.connect(self.Help)
        layout.addWidget(helpButton,0,2,Qt.AlignmentFlag.AlignTrailing)
        self.newButton = QPushButton("+")
        self.newButton.clicked.connect(self.NewVariable)
        layout.addWidget(self.newButton,layout.rowCount()+1,0,1,2)
        self.items: List[VarItem] = []
        for i in range(self.model.rowCount()):
            self.AddRow(layout, self.model.item(i))
    
    def AddRow(self, layout: QGridLayout, modelItem: VariableItem):
        newItem = VarItem(self, modelItem)
        self.items.append(newItem)
        
        i = layout.rowCount()-1
        layout.addWidget(newItem.textbox,i,0)
        layout.addWidget(newItem.dropdown,i,1)
        layout.addWidget(newItem.removeButton,i,2,Qt.AlignmentFlag.AlignTrailing)
        layout.addWidget(self.newButton,i+1,0,1,2)

    def NewVariable(self):
        newItem = self.model.newItem()
        self.AddRow(self.layout(), newItem)
        self.graph.canvas.update()   # Trigger repaint
        
    def RemoveVariable(self):
        for row, item in enumerate(self.items):
            if item.removeButton is self.sender():
                self.model.removeRow(row)
                self.items.remove(item)
                
                # NOTE this isn't actually removing the row from the grid layout but IDC
                self.layout().removeWidget(item.textbox)
                self.layout().removeWidget(item.dropdown)
                self.layout().removeWidget(item.removeButton)
                item.dropdown.deleteLater()  # Since still linked to other model?
                return
            
    def Help(self):
        QMessageBox.information(self, 'Help', "Wiki Help: <a href='https://github.com/BLCM/BLCMods/wiki/BPD-classroom' style='color:orange'>BLCMods BPD Classroom</a>"\
            "<p>This is a list of all variables linked by all Events and Behaviors."\
            "<p>This can be used to pass variables between nodes, by linking the variable output of one node to a variable input of another."\
            "<br>See ClassMod_Siren_Z_LegendarySiren for an simple example."
            "<p>Some behaviors like Behavior_SimpleMath even reassign an output value to the same variable that it input."\
            )


class VarItem:
    """ A group of widgets representing a single VariableData """
    def __init__(self, parent: VarsNode, modelItem: VariableItem):
        self.textbox = QLineEdit()
        self.textbox.setSizePolicy(QSizePolicy.Expanding,QSizePolicy.Expanding)
        self.dropdown = NodeCombo()
        self.dropdown.SetHover(HoveringOver.VAR_NODE_COMBO, HoveringOver.GRAPH_NODE)
        self.dropdown.setModel(parent.sequence.varTypeModel)
        self.removeButton = QPushButton("-")
        self.removeButton.clicked.connect(parent.RemoveVariable)

        model = parent.sequence.varModel
        self.mapper = QDataWidgetMapper()
        self.mapper.setModel(model)
        self.mapper.addMapping(self.textbox, 0)
        self.mapper.addMapping(self.dropdown, 1, b"currentIndex")
        self.mapper.setCurrentIndex(modelItem.row())
