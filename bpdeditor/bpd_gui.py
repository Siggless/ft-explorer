from __future__ import annotations
from typing import List
from bpdeditor.bpd_classes import *
import qdarkgraystyle
from PyQt5 import QtWidgets, QtGui, QtCore
from PyQt5.QtCore import QPoint, QRect

_DRAG_BUTTON = QtCore.Qt.LeftButton
_PAN_BUTTON = QtCore.Qt.RightButton

class HoveringOver(Enum):
    UNKNOWN=0
    BACKGROUND=1
    GRAPH_NODE=2
    OUT_LINK_BUTTON=3
    VAR_LINK_BUTTON=4

def midPoint(a:QPoint, b:QPoint):
    return (a+b)/2

class GraphCanvas(QtWidgets.QFrame):
    """ Canvas for our nodes - handles dragging, panning and painting connections """
    hover:HoveringOver=HoveringOver.BACKGROUND
    drawVarConnections:bool = True
    linkPenColor:QtGui.QColor = QtGui.QColorConstants.DarkRed
    
    def __init__(self):
        super().__init__()
        self.setFrameStyle(QtWidgets.QFrame.StyledPanel | QtWidgets.QFrame.Sunken)
        self.setLineWidth(5)
        self.setStyleSheet(self.styleSheet() + '\n*[selected="true"] { border: 2px solid orange; }')
        
        self.isSelecting=False
        self.selectStartPos=QPoint()
        self.selectEndPos=QPoint()
        self.selectedNodes=[]
        
        # Vars for drag operation - yeah bodgey
        self.isDragging=False
        self.dragObject=None
        self.dragObjectPos=QPoint()
        self.dragStartPos=QPoint()
        self.dragEndPos=QPoint()
        
        self.isPanning=False
        self.panStartPos=QPoint()
        self.panEndPos=QPoint()
    
    def FindNode(self, b:BehaviorData):
        """ Returns the node for the given BehaviorData object"""
        for child in self.findChildren(GraphNode):
            if hasattr(child,'data'):
                if child.data is b:
                    return child
    
    def MakeNodes(self, sequences):
        """
        Create the GraphNodes for all BehaviorSequences
        Assigning each node a sequenceID is a bit of an afterthought...
        """
        self.rootNode = GraphNode("BPD ROOT", -1, self)
        self.rootNode.setFixedSize(0,0)
        
        self.sequences = sequences
        self.sequenceVarNodes = []
        sequenceRootNodes = []
        for idx, seq in enumerate(sequences):
            sequenceRootNode = GraphNode("SEQUENCE ROOT", idx, self)
            sequenceRootNode.setFixedSize(0,0)
            sequenceRootNodes.append(sequenceRootNode)
            self.rootNode.outConnections.append(Connection(self.rootNode,-1,sequenceRootNode,-1))
            
            # First make a fake connection to this sequence's Variables node so it's on the left of the rest
            node = VarsNode(seq.VariableData, idx, self)
            self.sequenceVarNodes.append(node)
            sequenceRootNode.outConnections.append(Connection(sequenceRootNode, -1, node, -1))
            
            for event in seq.EventData2:
                node = EventNode(event, idx, self)
                sequenceRootNode.outConnections.append(Connection(sequenceRootNode,-1,node,-1))
            for beh in seq.BehaviorData2:
                node = BehaviorNode(beh, idx, self)

        self.MakeConnections()
        
        # Find "orphan" nodes that have no input connections and make fake connections
        for node in self.findChildren(BehaviorNode):
            if len(node.inConnections) == 0:
                sequenceRootNode.outConnections.append(Connection(sequenceRootNodes[node.sequenceID], -1, node, -1))
        
    def MakeConnections(self):
        """
        Create the connections between GraphData nodes
        Called on start once all nodes have been created
        """
        Connections = []
        for child in self.findChildren(GraphNode):
            if hasattr(child,'data'):
                for con in child.data.Outputs:
                    dest = self.FindNode(con.LinkedBehavior)
                    conny = Connection(child,0,dest,0)
                    Connections.append(conny)
                    child.outConnections.append(conny)
                    dest.inConnections.append(conny)
                for idx, link in enumerate(child.data.Variables):
                    if link.VariableLinkType != VariableLinkTypes.BVARLINK_Output:
                        for var in link.LinkedVariableList:
                            # Is this variable set from another node?
                            for node in self.findChildren(GraphNode):
                                if hasattr(node,'data'):
                                    for idx2, link2 in enumerate(node.data.Variables):
                                        if link2.VariableLinkType == VariableLinkTypes.BVARLINK_Output:
                                            for var2 in link2.LinkedVariableList:
                                                if var is var2:
                                                    child.varConnections.append(Connection(node,idx2,child,idx))
                                                    break
                        
               
    def OrganiseTree(self):
        """  
        Works well enough - checks for intersections on a node's level in the tree
        Assuming all nodes are the same height
        """

        for node in self.findChildren(GraphNode):
            node.hasBeenPositioned=False

        def TreePositioner(node:GraphNode, branchCentrePos:QPoint, level) -> QRect:
            """ 
            Positions the node based on its parent's current position, avoiding other nodes on its level
            Returns the bounding box for this node, after positioning
            """
            if node.hasBeenPositioned:
                # We've already hit this one so ignore
                return QRect()
            if len(levelBBoxes)<=level:
                levelBBoxes.append(QRect())
                
            node.move(branchCentrePos - QPoint(int(node.width()/2) ,0))
            branchDelta = QPoint()
            # Shift the position if intersecting with this row's bbox
            levelBox = levelBBoxes[level]
            intersectBox = levelBox.intersected(node.geometry())
            if intersectBox.width()>0:
                branchDelta = QPoint(levelBox.topRight().x()-node.geometry().x()+xPadding,0)
                branchCentrePos = branchCentrePos + branchDelta

            node.hasBeenPositioned=True # Here in case children loop back to this node
            
            numChildren = len(node.outConnections)
            if numChildren>0:
                allChildBox=QRect()
                xSpacing = node.outConnections[0].destNode.width()+xPadding
                for i in range(numChildren):
                    #newPos = branchCentrePos + QPoint(xSpacing*i, node.height()+yPadding)
                    newPos = branchCentrePos + QPoint(int(xSpacing*(i-(numChildren-1)/2)), node.height()+yPadding)
                    childBox = TreePositioner(node.outConnections[i].destNode, newPos, level+1)
                    allChildBox=allChildBox.united(childBox)
                branchCentrePos.setX(allChildBox.center().x())
            node.move(branchCentrePos - QPoint(int(node.width()/2) ,0))
            
            # And check for intersections AGAIN to improve cases where a child has multiple parents
            intersectBox = levelBox.intersected(node.geometry())
            if intersectBox.width()>0:
               node.move(QPoint(levelBox.topRight().x()+xPadding, branchCentrePos.y()))
                
            levelBox = levelBox.united(node.geometry())
            levelBBoxes[level] = levelBox
            return node.geometry()

        levelBBoxes:List[QRect] = []
        xPadding=50
        yPadding=50
            
        # OK let's do this
        TreePositioner(self.rootNode, QPoint(0,-yPadding), 0)
                
        self.scroll(-self.childrenRect().topLeft().x(),0)
    
    def ExpandAll(self):
        """
        Expands all variable and outputlink lists on all nodes, then reorganises the tree
        """
        for node in self.findChildren(GraphNode):
             if hasattr(node,'varLinkList'): node.varLinkList.show()
             if hasattr(node,'outLinkList'): node.outLinkList.show()
             node.adjustSize()
             node.updateGeometry()
        self.sender().setChecked(True)
        self.OrganiseTree()
        # If a node is selected then jump back to that
        if len(self.selectedNodes) > 0:
            node = self.selectedNodes[0]
            self.scroll(self.rect().center().x()-node.geometry().center().x(),self.rect().center().y()-node.geometry().center().y())
        
    def CollapseAll(self):
        """
        Collapses all variable and outputlink lists on all nodes, then reorganises the tree
        """
        for node in self.findChildren(GraphNode):
             if hasattr(node,'varLinkList'): node.varLinkList.hide()
             if hasattr(node,'outLinkList'): node.outLinkList.hide()
             node.adjustSize()
        self.sender().setChecked(True)
        self.OrganiseTree()
        # If a node is selected then jump back to that
        if len(self.selectedNodes) > 0:
            node = self.selectedNodes[0]
            self.scroll(self.rect().center().x()-node.geometry().center().x(),self.rect().center().y()-node.geometry().center().y())
    
    def ClearSelection(self):
        for node in self.selectedNodes:
            node.isSelected=False
            node.setProperty("selected", "false")
            node.setStyleSheet(self.styleSheet())
        self.selectedNodes=[]
        self.isSelecting=False
    
    def paintEvent(self, event):
        """ Handles painting connections and input rectangles """
        super().paintEvent(event)
        
        # Draw all connections
        qp = QtGui.QPainter(self)
        defaultPen = qp.pen()   # From style to keep light/dark mode
        defaultPen.setWidth(2)
        for child in self.findChildren(GraphNode):
            if child.width()<=0: continue   # Don't draw root nodes
            
            # Variable Links
            if hasattr(child,'varLinkList'):
                if self.drawVarConnections or child.isSelected:
                    # Unselected nodes have alpha to make it less painful
                    if not child.isSelected:
                        self.linkPenColor.setAlpha(100)
                    else:
                        self.linkPenColor.setAlpha(255)
                    qp.setPen(QtGui.QPen(self.linkPenColor))
                    
                    varNode = self.sequenceVarNodes[child.sequenceID]
                    for link in child.varLinkList.items:
                        for varDropdown in link[1]:
                            # Get the dropdown index - that should match the row id in the vars node
                            id = varDropdown.currentIndex()
                            if id >=0 and len(varNode.items)>id:
                                varRowButton = varNode.items[id][-1]
                                
                                posTo = midPoint(varRowButton.mapTo(self,varRowButton.rect().topRight()),varRowButton.mapTo(self,varRowButton.rect().bottomRight()))
                                if varNode.mapTo(self,varNode.rect().center()).x()<child.mapTo(self,child.rect().center()).x():
                                    posTo.setX(varNode.mapTo(self,varNode.rect().topRight()).x())
                                else:
                                    posTo.setX(varNode.mapTo(self,varNode.rect().topLeft()).x())
                                
                                if not child.varLinkList.isVisible():
                                    # If vars not expanded then draw from button
                                    button = child.varLinkButton
                                    posFrom = midPoint(button.mapTo(self,button.rect().topLeft()),button.mapTo(self,button.rect().bottomLeft()))
                                else:
                                    # If vars list is expanded then draw from items
                                    posFrom = midPoint(varDropdown.mapTo(self,varDropdown.rect().topLeft()),varDropdown.mapTo(self,varDropdown.rect().bottomLeft()))
                                    
                                if varNode.mapTo(self,varNode.rect().center()).x()<child.mapTo(self,child.rect().center()).x():
                                    posFrom.setX(child.mapTo(self,child.rect().topLeft()).x())
                                else:
                                    posFrom.setX(child.mapTo(self,child.rect().topRight()).x())
                                qp.drawLine(posFrom,posTo)
                                
            # Output-to-Input Variables
            self.linkPenColor.setAlpha(230)
            qp.setPen(QtGui.QPen(self.linkPenColor,2))
            for con in child.varConnections:
                qp.drawLine(midPoint(con.sourceNode.geometry().bottomLeft(),con.sourceNode.geometry().bottomRight())+QPoint(14*(con.sourceIndex+1),0),midPoint(con.destNode.geometry().topLeft(),con.destNode.geometry().topRight())+QPoint(14*(con.destIndex+1),0))
            # Output Links
            qp.setPen(defaultPen)
            for con in child.outConnections:
                qp.drawLine(midPoint(con.sourceNode.geometry().bottomLeft(),con.sourceNode.geometry().bottomRight()),midPoint(con.destNode.geometry().topLeft(),con.destNode.geometry().topRight()))
        
        if self.isSelecting:
            if self.selectEndPos:
                qp.setBrush(QtGui.QBrush(QtGui.QColor(100, 10, 10, 40)))
                selectangle = QRect(self.selectStartPos, self.selectEndPos)
                qp.drawRect(selectangle)
                qp.drawText(20,20,"Selecting - Right click to cancel")
                qp.drawText(20,40,str(self.selectEndPos))
        elif self.isDragging:
            qp.setBrush(QtGui.QBrush(QtGui.QColor(100, 10, 10, 40)))
            dragVector = self.dragEndPos - self.dragStartPos
            for node in self.selectedNodes:
                qp.drawRect(QRect(node.pos()+dragVector, node.pos()+dragVector + QPoint(node.width(), node.height())))
            qp.drawLine(self.dragStartPos, self.dragEndPos)
            qp.drawText(20,20,"Moving Node - Right click to cancel")
            qp.drawText(20,40,str(self.dragEndPos))
        elif self.isPanning:
            qp.drawText(20,20,"Panning")
            qp.drawText(20,40,str(self.panStartPos))
        else:
            if self.hover == HoveringOver.BACKGROUND:
                qp.drawText(20,20,"Left mouse - Select")
                qp.drawText(20,40,"Right mouse - Pan view")
            elif self.hover == HoveringOver.GRAPH_NODE:
                qp.drawText(20,20,"Left mouse - Select / Move node")
            elif self.hover == HoveringOver.VAR_LINK_BUTTON:
                qp.drawText(20,20,"Left mouse - Toggle variable link info")
            elif self.hover == HoveringOver.OUT_LINK_BUTTON:
                qp.drawText(20,20,"Left mouse - Toggle output link info")
        
    def mousePressEvent(self, event):
        if not self.dragObject:
            if event.button() == _PAN_BUTTON:
                self.isPanning=True
                self.panStartPos = event.pos()
                self.update()
            elif event.button() == _DRAG_BUTTON:
                self.isSelecting=True
                self.selectStartPos = event.pos()
                self.selectEndPos = None
    
    def mouseMoveEvent(self, event):   
        if event.buttons() == _PAN_BUTTON and self.isPanning:
            self.panEndPos = event.pos()
            self.scroll(self.panEndPos.x()-self.panStartPos.x(), self.panEndPos.y()-self.panStartPos.y())
            # Yeah bodgey updating pos. Could be an applied QTransform from fixed startPos
            self.panStartPos=self.panEndPos
            self.update()
            return
        
        if event.buttons() == _DRAG_BUTTON:
            if self.isSelecting:
                self.selectEndPos = event.pos()
                self.update()
            if self.isDragging:
                if (event.pos().x()>0 and event.pos().y()>0 and event.pos().x()<self.width() and event.pos().y()<self.height()):
                    self.dragEndPos = event.pos()
                    self.update()
            elif self.dragObject and ((event.pos() - self.dragStartPos).manhattanLength() >= QtWidgets.QApplication.startDragDistance()):
                self.isDragging = True
    
    def mouseReleaseEvent(self, event):
        if event.button() == _DRAG_BUTTON:
            if self.isDragging:
                dragVector = self.dragEndPos - self.dragStartPos
                for node in self.selectedNodes:
                    node.move(node.pos()+dragVector)
                self.isDragging=False
            elif self.isSelecting:
                self.ClearSelection()
                if self.selectEndPos:
                    # Select all nodes in the selection rectangle, the *selectangle*, if you will...
                    selectangle = QRect(self.selectStartPos, event.pos())
                    for node in self.findChildren(GraphNode):
                        if selectangle.contains(QRect(node.pos(),node.size())):
                            if node not in self.selectedNodes:
                                self.selectedNodes.append(node)
                                node.isSelected=True
                                node.setProperty("selected","true")
                                node.setStyleSheet(self.styleSheet())
        
        if event.button() == _PAN_BUTTON:
            self.isDragging=False
            self.isPanning=False
            self.panStartPos=None
            
        self.isSelecting=False
        self.dragObject=None
        self.update()

"""
Abstract Node Classes
Mostly to handles user inputs on all nodes
"""
class GraphNode(QtWidgets.QGroupBox):
    """ Base Node class """
    def __init__(self, title, seqID, parent):
        super().__init__(title, parent)
        self.parent = parent
        self.setSizePolicy(QtWidgets.QSizePolicy.Policy.Minimum, QtWidgets.QSizePolicy.Policy.Expanding)
        self.sequenceID:int = seqID # To filter to the correct sequence for links

        self.inConnections=[]
        self.outConnections=[]
        self.varConnections=[]  # Connection to other node that gives an output to a variable we input
        self.treeLevel=None
        self.treeWidth=None
        self.hasBeenPositioned:bool = False
        self.isSelected:bool = False
        
    def mousePressEvent(self, event):
        self.raise_()
        self.adjustSize()
        if event.button() == _DRAG_BUTTON:
            self.parent.dragObject=self
            self.parent.dragObjectPos = event.pos()
            self.parent.dragStartPos = event.pos()+self.pos()
            if self not in self.parent.selectedNodes:
                self.parent.ClearSelection()
                self.isSelected=True
                self.parent.selectedNodes.append(self)
                self.setProperty("selected","true")
                self.parent.setStyleSheet(self.parent.styleSheet())
            
    def enterEvent(self, event):
        self.parent.hover = HoveringOver.GRAPH_NODE
        self.parent.update()
    def leaveEvent(self, event):
        self.parent.hover = HoveringOver.BACKGROUND
        self.parent.update()

class NodeButton(QtWidgets.QPushButton):
    """ Just a button, but has override enter and leave events to update our tooltips """
    def __init__(self, text:str, enterHover:HoveringOver = HoveringOver.UNKNOWN, leaveHover:HoveringOver = HoveringOver.UNKNOWN):
        super().__init__(text)
        self.setHover(enterHover, leaveHover)
        
    def setHover(self, enterHover:HoveringOver = HoveringOver.UNKNOWN, leaveHover:HoveringOver = HoveringOver.UNKNOWN):
        self.enterHover:HoveringOver = enterHover
        self.leaveHover:HoveringOver = leaveHover
    
    def mouseReleaseEvent(self, event):
        super().mouseReleaseEvent(event)
        self.parentWidget().raise_()
        self.parentWidget().update()
        self.parentWidget().adjustSize()
    
    def enterEvent(self, event):
        if self.parentWidget().parent:
            self.parentWidget().parent.hover=self.enterHover
            self.parentWidget().parent.update()
    def leaveEvent(self, event):
        if self.parentWidget().parent:
            self.parentWidget().parent.hover=self.leaveHover
            self.parentWidget().parent.update()


"""
BPD Specific Node Classes
"""

class EventNode(GraphNode):
    def __init__(self, data:EventData, seqID, parent):
        super().__init__("Event", seqID, parent)
        self.data:EventData=data
        atts:EventUserData = data.UserData
        
        # This should prob be a QStandardItemModel but a really can't get my head round that
        l0=QtWidgets.QLabel("EventName")
        self.p0=QtWidgets.QLineEdit(atts.EventName)
        l1=QtWidgets.QLabel("bEnabled")
        self.p1=QtWidgets.QCheckBox()
        self.p1.setCheckState(QtCore.Qt.CheckState.Checked if atts.bEnabled else QtCore.Qt.CheckState.Unchecked)
        l2=QtWidgets.QLabel("bReplicate")
        self.p2=QtWidgets.QCheckBox()
        self.p2.setCheckState(QtCore.Qt.CheckState.Checked if atts.bReplicate else QtCore.Qt.CheckState.Unchecked)
        l3=QtWidgets.QLabel("MaxTriggerCount")
        self.p3=QtWidgets.QLineEdit(str(atts.MaxTriggerCount))
        l4=QtWidgets.QLabel("ReTriggerDelay")
        self.p4=QtWidgets.QLineEdit(str(atts.ReTriggerDelay))
        
        layout = QtWidgets.QGridLayout(self)
        layout.addWidget(l0,0,0)
        layout.addWidget(self.p0,0,1)
        layout.addWidget(l1,1,0)
        layout.addWidget(self.p1,1,1)
        layout.addWidget(l2,2,0)
        layout.addWidget(self.p2,2,1)
        layout.addWidget(l3,3,0)
        layout.addWidget(self.p3,3,1)        
        layout.addWidget(l4,4,0)
        layout.addWidget(self.p4,4,1)
        
        self.varLinkList:VarLinksList = VarLinksList(self, data.Variables)
        self.outLinkList:OutputLinksList = OutputLinksList(self, data.Outputs)
        self.varLinkButton = NodeButton("Variables", HoveringOver.VAR_LINK_BUTTON, HoveringOver.GRAPH_NODE)
        self.varLinkButton.clicked.connect(self.VarLinkToggle)
        self.outLinkButton = NodeButton("Output Links", HoveringOver.OUT_LINK_BUTTON, HoveringOver.GRAPH_NODE)
        self.outLinkButton.clicked.connect(self.OutLinkToggle)
        self.varLinkButton.rect().left
        layout.addWidget(self.varLinkButton,5,0,1,2)
        layout.addWidget(self.varLinkList,6,0,1,2)
        layout.addWidget(self.outLinkButton,7,0,1,2)
        layout.addWidget(self.outLinkList,8,0,1,2)
        
    def VarLinkToggle(self):
        if self.varLinkList.isVisible():
            self.varLinkList.hide()
        else:
            self.varLinkList.show()
        self.parent.update()
        self.adjustSize()
        
    def OutLinkToggle(self):
        if self.outLinkList.isVisible():
            self.outLinkList.hide()
        else:
            self.outLinkList.show()
        self.parent.update()
        self.adjustSize()

class BehaviorNode(GraphNode):
    def __init__(self, data:BehaviorData, seqID, parent):
        super().__init__("Behavior", seqID, parent)
        self.data:BehaviorData = data
       
        l0=QtWidgets.QLabel("Class")
        self.p0=QtWidgets.QLineEdit(self.data.BehaviorClass)
        l1=QtWidgets.QLabel("Object")
        self.p1=QtWidgets.QLineEdit(self.data.BehaviorObject)
        
        layout = QtWidgets.QGridLayout(self)
        layout.addWidget(l0,0,0)
        layout.addWidget(self.p0,0,1)
        layout.addWidget(l1,1,0)
        layout.addWidget(self.p1,2,0,1,2)
        
        self.varLinkList:VarLinksList = VarLinksList(self, data.Variables)
        self.outLinkList:OutputLinksList = OutputLinksList(self, data.Outputs)
        self.varLinkButton = NodeButton("Variables", HoveringOver.VAR_LINK_BUTTON, HoveringOver.GRAPH_NODE)
        self.varLinkButton.clicked.connect(self.VarLinkToggle)
        self.outLinkButton = NodeButton("Output Links", HoveringOver.OUT_LINK_BUTTON, HoveringOver.GRAPH_NODE)
        self.outLinkButton.clicked.connect(self.OutLinkToggle)
        
        layout.addWidget(self.varLinkButton,3,0,1,2)
        layout.addWidget(self.varLinkList,4,0,1,2)
        layout.addWidget(self.outLinkButton,5,0,1,2)
        layout.addWidget(self.outLinkList,6,0,1,2)
        
    def VarLinkToggle(self):
        if self.varLinkList.isVisible():
            self.varLinkList.hide()
        else:
            self.varLinkList.show()
        
    def OutLinkToggle(self):
        if self.outLinkList.isVisible():
            self.outLinkList.hide()
        else:
            self.outLinkList.show()

class VarLinksList(QtWidgets.QFrame):
    """ The expandable widget list for each variable link. """
    def __init__(self, parent:QtWidgets.QWidget, variables):
        super().__init__(parent)
        self.parent=parent
        self.linkData = variables
        
        self.hide()
        layout = QtWidgets.QGridLayout(self)
        # Headers
        layout.addWidget(QtWidgets.QLabel("Property Name"),0,0)
        layout.addWidget(QtWidgets.QLabel("Link Type"),0,1)
        layout.addWidget(QtWidgets.QLabel("Connection Index"),0,2)
        helpButton = QtWidgets.QPushButton("?")
        helpButton.clicked.connect(self.HelpVariables)
        layout.addWidget(helpButton,0,3,QtCore.Qt.AlignmentFlag.AlignTrailing)
        self.items=[]
        for link in self.linkData:
            self.AddRow(layout,link)
    
    def AddRow(self, layout:QtWidgets.QGridLayout, link:VariableLinkData):
        nameBox = QtWidgets.QLineEdit(str(link.PropertyName))
        dropdown = QtWidgets.QComboBox()
        dropdown.addItems(VariableLinkTypes._member_names_[0:VariableLinkTypes.BVARLINK_MAX.value])
        dropdown.setCurrentIndex(link.VariableLinkType.value)
        idBox = QtWidgets.QLineEdit(str(link.ConnectionIndex))
        
        i = layout.rowCount()
        layout.addWidget(nameBox,i,0)
        layout.addWidget(dropdown,i,1)
        layout.addWidget(idBox,i,2)

        # Add multiple combo-boxes populated with the vars list from that node
        varDropdownList=[]
        if len(link.LinkedVariableList)>0:
            for idx, var in enumerate(link.LinkedVariableList):
                varDropdown = QtWidgets.QComboBox()
                # TODO get this list from the current vars node list...
                varDropdown.addItems(f"{str(i)} - {v.Name} - {str(v.Type.name)}" for i,v in enumerate(link.variableList))
                varDropdown.setCurrentIndex(idx + link.consolidatedList[parse_arrayindexandlength(link.LinkedVariables)[0]])
                varDropdownList.append(varDropdown)
                i = i + 1
                layout.addWidget(varDropdown,i,0,1,3)
        else:
            # Still add a blank
            varDropdown = QtWidgets.QComboBox()
            varDropdown.addItems(f"{str(i)} - {textbox.text()} - {str(dropdown.currentText())}" for i, (var,textbox,dropdown) in enumerate(self.parent.parent.sequenceVarNodes[self.parent.sequenceID].items))
            varDropdownList.append(varDropdown)
            i = i + 1
            layout.addWidget(varDropdown,i,0,1,3)

        self.items.append((link.LinkedVariableList,varDropdownList,nameBox,dropdown,idBox))

    def HelpVariables(self):
        QtWidgets.QMessageBox.information(self, 'Help', "Wiki Help: <a href='https://github.com/BLCM/BLCMods/wiki/BPD-classroom' style='color:orange'>BLCMods BPD Classroom</a>"\
            "<p>Where do the variables come from?"\
            "<p>For Behaviors, see the class attributes in the UnrealScript for this behavior class. For variable ouputs, see the PublishBehaviorOutput() method."\
            "<br>From the BehaviorBase class, it looks like Property Names DO need to match."\
            "<p>For Events, find the method with the name of the event in the parent class of the BPD."\
            " For example, ShieldDefinition has OnAmmoAbsorbed()."\
            "<br>Look inside WillowGame.upk, GearboxFramework.upk or Engine.upk,"\
            " using <a href='https://github.com/BLCM/BLCMods/wiki#modders-tools' style='color:orange'>UE Explorer</a>."\
            "<p>Connection Index?"\
            "<p>These only seem to be used for Events, where they are maybe the parameter index for the method, instead of matching the Property Name? IDK why are you listening to me?"\
            )

class OutputLinksList(QtWidgets.QFrame):
    """ The expandable widget list for each output link. """
    def __init__(self, parent:QtWidgets.QWidget, outputs):
        super().__init__(parent)
        self.parent=parent
        self.linkData = outputs
        
        self.hide()
        layout = QtWidgets.QGridLayout(self)
        # Headers
        layout.addWidget(QtWidgets.QLabel("Link ID"),0,0)
        layout.addWidget(QtWidgets.QLabel("Active Delay"),0,1)
        helpButton = QtWidgets.QPushButton("?")
        helpButton.clicked.connect(self.HelpOutputs)
        layout.addWidget(helpButton,0,2,QtCore.Qt.AlignmentFlag.AlignTrailing)
        self.items=[]
        for link in self.linkData:
            self.AddRow(layout,link)
    
    def AddRow(self, layout:QtWidgets.QGridLayout, link:OutputLinkData):
        idBox = QtWidgets.QLineEdit(str(link.LinkId))
        delayBox = QtWidgets.QLineEdit(str(link.ActiveDelay))
        textbox = QtWidgets.QLineEdit(link.LinkedBehavior.BehaviorObject if link.LinkedBehavior else "null")
        self.items.append((link,textbox,idBox,delayBox))
        
        i = layout.rowCount()
        layout.addWidget(idBox,i,0)
        layout.addWidget(delayBox,i,1)
        layout.addWidget(textbox,i+1,0,1,2)

    def HelpOutputs(self):
        QtWidgets.QMessageBox.information(self, 'Help', "Wiki Help: <a href='https://github.com/BLCM/BLCMods/wiki/BPD-classroom' style='color:orange'>BLCMods BPD Classroom</a>"\
            "<p>What do?"\
            "<p>ActivateDelay is the time delay before this output fires."\
            "<p>LinkID is used on some behavior classes. This can be used to choose between output links - not firing them all."\
            "<br>Look in the behavior's UnrealScript class - they actually list the linkIDs with descriptions in the defaultproperties{} struct, and you can see where the ActivateBehaviorOutputLink() method is called in the code with a linkID."\
            "<br><br>Behavior_IntSwitchRange uses it to decide which output to fire."\
            "<br>Behavior_DamageSourceSwitch uses it to restrict damage types."\
            "<br>Behavior_TriggerDialogEvent uses it loop the behavior until the dialogue is finished... maybe?"\
            "<br>Some have a linkID of -1. ¯\\_(ツ)_/¯"\
            )

class VarsNode(GraphNode):
    def __init__(self, varData, seqID, parent):
        super().__init__("Variables", seqID,parent)
        self.varData = varData
        
        layout = QtWidgets.QGridLayout(self)
        layout.addWidget(QtWidgets.QLabel("Name"),0,0)
        layout.addWidget(QtWidgets.QLabel("Type"),0,1)
        helpButton = QtWidgets.QPushButton("?")
        helpButton.clicked.connect(self.Help)
        layout.addWidget(helpButton,0,2,QtCore.Qt.AlignmentFlag.AlignTrailing)
        self.items=[]
        for var in varData:
            self.AddRow(layout,var)
    
    def AddRow(self, layout:QtWidgets.QGridLayout, var:VariableData):
        textbox = QtWidgets.QLineEdit(var.Name)
        textbox.setSizePolicy(QtWidgets.QSizePolicy.Expanding,QtWidgets.QSizePolicy.Expanding)
        dropdown = QtWidgets.QComboBox()
        dropdown.addItems(VariableTypes._member_names_[0:VariableTypes.BVAR_MAX.value])
        dropdown.setCurrentIndex(var.Type.value)
        self.items.append((var,textbox,dropdown))
        
        i = layout.rowCount()
        layout.addWidget(textbox,i,0)
        layout.addWidget(dropdown,i,1)
            
    def Help(self):
        QtWidgets.QMessageBox.information(self, 'Help', "Wiki Help: <a href='https://github.com/BLCM/BLCMods/wiki/BPD-classroom' style='color:orange'>BLCMods BPD Classroom</a>"\
            "<p>This is a list of all variables linked by all Events and Behaviors."\
            "<p>This can be used to pass variables between nodes, by linking the variable output of one node to a variable input of another."\
            "<br>See ClassMod_Siren_Z_LegendarySiren for an simple example."
            "<p>Some nodes like Behavior_SimpleMath even reassign an output value to the same variable that it input."\
            )

@dataclass
class Connection():
    sourceNode:GraphNode
    sourceIndex:int
    destNode:GraphNode
    destIndex:int


class MainToolBar(QtWidgets.QToolBar):
    """
    Toolbar to hold a few toggles for us
    """

    def __init__(self, parent):

        super().__init__(parent)

        self.action_dark = self.addAction('Dark Theme', parent.toggle_dark)
        self.action_dark.setCheckable(True)
        self.action_dark.setChecked(parent.settings.value('toggles/darktheme', False, type=bool))

        # Graph settings
        self.action_expand = self.addAction('Expand All', parent.graphFrame.ExpandAll)
        self.action_expand.setCheckable(True)
        self.action_expand.setChecked(True)
        self.action_collapse = self.addAction('Collapse All', parent.graphFrame.CollapseAll)
        self.action_collapse.setCheckable(True)
        self.action_collapse.setChecked(True)
        self.action_links = self.addAction('Show Variable Links', parent.toggle_links)
        self.action_links.setCheckable(True)
        self.action_links.setChecked(parent.settings.value('bpdwindow/showLinks', False, type=bool))


class BPDWindow(QtWidgets.QMainWindow):
    """
    BPD editor window
    I'm copying as much as I can from the main gui.py
    """

    def __init__(self, settings, app):
        super().__init__()
        
        # Store our data
        self.settings = settings
        self.app = app

        # Set some window properties 
        self.setMinimumSize(700, 500)
        self.resize(
            self.settings.value('bpdwindow/width', 700, type=int),
            self.settings.value('bpdwindow/height', 500, type=int)
            )
        self.setWindowTitle('BPD Editor')

        # Set up Ctrl-Q to quit
        shortcut = QtWidgets.QShortcut(QtGui.QKeySequence(QtCore.Qt.CTRL + QtCore.Qt.Key_Q), self)
        shortcut.activated.connect(self.action_quit)

        # Load the main frame
        self.graphFrame = GraphCanvas()
        self.setCentralWidget(self.graphFrame)
        self.graphFrame.drawVarConnections = self.settings.value('bpdwindow/showLinks', False, type=bool)
        
        # Load our toolbar
        self.toolbar = MainToolBar(self)
        self.addToolBar(self.toolbar)
     
        # Call out to a couple toggle functions, so that we're
        # applying our saved QSettings.  There's more elegant ways
        # to be doing this, but whatever.
        self.toggle_dark()


    def toggle_dark(self):
        """
        Toggles our dark theme
        """
        do_dark = self.toolbar.action_dark.isChecked()
        self.settings.setValue('toggles/darktheme', do_dark)
        if do_dark:
            self.app.setStyleSheet(qdarkgraystyle.load_stylesheet_pyqt5())
            self.graphFrame.linkPenColor=QtGui.QColorConstants.Red
            self.graphFrame.linkPenColor=QtGui.QColorConstants.Svg.orangered
            #self.graphFrame.linkPenColor=QtGui.QColorConstants.Svg.darkorange
        else:
            self.app.setStyleSheet('')
            self.graphFrame.linkPenColor=QtGui.QColorConstants.DarkRed
        # Adjust sizes for different stype margins etc
        for node in self.graphFrame.findChildren(GraphNode):
            node.adjustSize()
    
    def toggle_links(self):
        """
        Toggles whether link data is shown
        """
        self.settings.setValue('bpdwindow/showLinks', self.sender().isChecked())
        self.graphFrame.drawVarConnections = self.sender().isChecked()
        self.graphFrame.update()
        
    def action_quit(self):
        """
        Close the window
        """
        self.close()

    def closeEvent(self, event):
        """
        Save our window state
        """
        self.settings.setValue('bpdwindow/width', self.size().width())
        self.settings.setValue('bpdwindow/height', self.size().height())

    def is_valid_node(node) -> bool:
        """
        Returns:
            bool: Whether this node is supported by the editor
        """
        if not node:
            return False
        if not node.has_data:
            return False
        if len(node.data)<2 or 'BehaviorProviderDefinition' not in node.data[1]:
            return False
        if not 'BehaviorSequences' in node.get_structure():
            return False
        return True

    def set_node(self, node):
        """
        Sets the current data node
        """
        
        # Checks for whether the current node is a BPD
        if not BPDWindow.is_valid_node(node):
            return
        
        # OK this is a BPD, so set the BPD data
        self.node = node    # Might be useful to have children if we can help with linked behaviors
        self.bpd = node.get_structure()
        self.sequences = [BehaviorSequence(i) for i in self.bpd['BehaviorSequences']]
        self.graphFrame.MakeNodes(self.sequences)

        