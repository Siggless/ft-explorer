from typing import List
import qdarkgraystyle
from bpdeditor.bpd_classes import *
from bpdeditor.bpd_export_window import BPDExportWindow
from PyQt5.QtWidgets import *
from PyQt5.QtGui import *
from PyQt5.QtCore import *

"""
This file contains everything for the main BPD Editor window.
The BPD-specific nodes should probably be split into their own thing.
I reckon naive implementations. In particular these classes handle
 updating the data and eachother when something is changed.
 Should prob be a proper view-model that emits signals so we aren't
 manually looping through all nodes so much here.
Would be nice to use a proper QGraphicsScene to be able to zoom in
 and out, but that's beyond me. Nick something like NodeGraphQT.
"""

# Load our generated json dictionaries for auto-completers and var link suggestions
import json, inspect
from os import path
#behaviorFilePath = path.join("bpdeditor/behaviors.json")
behaviorFilePath = path.join(path.dirname(path.abspath(inspect.getfile(inspect.currentframe()))) , "behaviors.json")
behaviorDict = json.load(open(behaviorFilePath))
behaviorDict={ k:v for k,v in sorted(behaviorDict.items()) }    # Sort alphabetically
#eventFilePath = path.join("bpdeditor/behaviors.json")
eventFilePath = path.join(path.dirname(path.abspath(inspect.getfile(inspect.currentframe()))), "events.json")
eventDictFull:dict = json.load(open(eventFilePath))
eventDictFull={ k:v for k,v in sorted(eventDictFull.items()) }   # Sort alphabetically
# There are a lot of junk events so filter this one for the Completers
eventWhitelist = ["On","Damaged","Killed"]
eventDict={ k:v for k,v in eventDictFull.items() if any(k.startswith(prefix) for prefix in eventWhitelist) }


_PRIMARY_BUTTON = Qt.LeftButton
_SECONDARY_BUTTON = Qt.RightButton

class HoveringOver(Enum):
    UNKNOWN=0
    BACKGROUND=1
    GRAPH_NODE=2
    OUT_LINK_BUTTON=3
    VAR_LINK_BUTTON=4
    OUT_LINK_COMBO=5
    VAR_LINK_COMBO=6
    VAR_NODE_COMBO=7

def midPoint(a:QPoint, b:QPoint):
    return (a+b)/2

class GraphCanvas(QFrame):
    """
    Canvas for our nodes.
    Handles inputs, painting connections, and most operations.
    """
    hover:HoveringOver=HoveringOver.BACKGROUND
    drawVarConnections:bool = True
    linkPenColor:QColor = QColorConstants.DarkRed
    
    def __init__(self):
        super().__init__()
        self.setFrameStyle(QFrame.StyledPanel | QFrame.Sunken)
        self.setLineWidth(5)
        self.setStyleSheet(self.styleSheet() + '\n*[selected="true"] { border: 2px solid orange; }')
        self.tooltipLabel = QLabel(self)
        self.tooltipLabel.move(0,0)

        self.isSelecting=False
        self.selectStartPos=QPoint()
        self.selectEndPos=QPoint()
        self.selectedNodes=[]
        self.lastSelectedSequenceGraph:SequenceGraph = None
        
        # Vars for drag operation - yeah bodgey
        self.isDragging=False
        self.dragObject=None
        self.dragObjectPos=QPoint()
        self.dragStartPos=QPoint()
        self.dragEndPos=QPoint()
        
        self.isPanning=False
        self.panStartPos=QPoint()
        self.panEndPos=QPoint()
        
        self.isLinking=False
        self.linkSource=None
        self.linkDest=None
        
    
    def MakeNodes(self, sequences):
        """
        Create the GraphNodes for all BehaviorSequences
        """
        self.rootNode = GraphNode("BPD ROOT", None, self)
        self.rootNode.setFixedSize(0,0)
        
        self.sequences = sequences
        self.sequenceGraphs = []
        for seq in sequences:
            sequenceGraph = SequenceGraph(self,seq)
            self.sequenceGraphs.append(sequenceGraph)
            sequenceGraph.MakeNodes()
            self.rootNode.outConnections.append(Connection(self.rootNode,-1,sequenceGraph.rootNode,-1))
               
    def OrganiseTree(self):
        """  
        Works well enough - checks for intersections on a node's level in the tree.
        Assuming all nodes are the same height (so levels don't overlap)
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
    
    def ClearCanvas(self):
        """ Removes all graphs and nodes """
        for child in self.findChildren(GraphNode):
            child.deleteLater()
            self.sequences=None
            self.sequenceGraphs=None
            self.lastSelectedSequenceGraph=None
            self.rootNode=None
            self.selectedNodes=[]
    
    def ExpandAll(self):
        """
        Expands all variable and outputlink lists on all nodes, then reorganises the tree
        """
        for node in self.findChildren(SequenceNode):
             node.varLinkList.show()
             node.outLinkList.show()
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
        for node in self.findChildren(SequenceNode):
             node.varLinkList.hide()
             node.outLinkList.hide()
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
        self.parent().toolbar.action_delete.setCheckable(False)
        self.parent().toolbar.action_delete.setChecked(False)
    
    def DeleteSelectedNodes(self):
        for node in reversed(self.selectedNodes):
            if issubclass(type(node),SequenceNode):
                node.isSelected=False
                self.selectedNodes.remove(node)
                node.Delete()
        self.parent().toolbar.action_delete.setCheckable(False)
        self.parent().toolbar.action_delete.setChecked(False)
    
    def NewEventNode(self):
        if self.lastSelectedSequenceGraph:
            self.lastSelectedSequenceGraph.NewEventNode()
        self.parent().toolbar.action_new_event.setChecked(True)
    
    def NewBehaviorNode(self):
        if self.lastSelectedSequenceGraph:
            self.lastSelectedSequenceGraph.NewBehaviorNode()
        self.parent().toolbar.action_new_behavior.setChecked(True)
    
    
    def paintEvent(self, event):
        """ Handles painting connections, input rectangles and tooltips """
        super().paintEvent(event)
        
        # Draw all connections
        qp = QPainter(self)
        defaultPen = qp.pen()   # From style to keep light/dark mode
        defaultPen.setWidth(2)
        for seqGraph in self.sequenceGraphs:
            for child in seqGraph.sequenceNodes + [seqGraph.varNode]:
                #if child.width()<=0: continue   # Don't draw root nodes
                
                # Variable Links
                if hasattr(child,'varLinkList'):
                    if self.drawVarConnections or child.isSelected:
                        # Unselected nodes have alpha to make it less painful
                        if not child.isSelected:
                            self.linkPenColor.setAlpha(100)
                        else:
                            self.linkPenColor.setAlpha(255)
                        qp.setPen(QPen(self.linkPenColor))
                        
                        varNode = seqGraph.varNode
                        for link in child.varLinkList.items:
                            for varDropdown in link.varDropdownList:
                                # Get the dropdown index - that should match the row id in the vars node
                                id = varDropdown.currentIndex()
                                if id >=0 and len(varNode.items)>id:
                                    varRowButton = varNode.items[id].removeButton
                                    
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
                qp.setPen(QPen(self.linkPenColor,2))
                for con in child.varConnections:
                    qp.drawLine(midPoint(con.sourceNode.geometry().bottomLeft(),con.sourceNode.geometry().bottomRight())+QPoint(14*(con.sourceIndex+1),0),midPoint(con.destNode.geometry().topLeft(),con.destNode.geometry().topRight())+QPoint(14*(con.destIndex+1),0))
                # Output Links
                qp.setPen(defaultPen)
                for con in child.outConnections:
                    qp.drawLine(midPoint(con.sourceNode.geometry().bottomLeft(),con.sourceNode.geometry().bottomRight()),midPoint(con.destNode.geometry().topLeft(),con.destNode.geometry().topRight()))
        # END for each sequenceGraph
        
        tooltipText:str = ""
        if self.isSelecting:
            if self.selectEndPos:
                qp.setBrush(QBrush(QColor(100, 10, 10, 40)))
                selectangle = QRect(self.selectStartPos, self.selectEndPos)
                qp.drawRect(selectangle)
                tooltipText = "Selecting - Right click to cancel"
                tooltipText += "\n" + str(self.selectEndPos)
        elif self.isDragging:
            qp.setBrush(QBrush(QColor(100, 10, 10, 40)))
            dragVector = self.dragEndPos - self.dragStartPos
            for node in self.selectedNodes:
                qp.drawRect(QRect(node.pos()+dragVector, node.pos()+dragVector + QPoint(node.width(), node.height())))
            qp.drawLine(self.dragStartPos, self.dragEndPos)
            tooltipText = "Moving Node - Right click to cancel"
            tooltipText += "\n" + str(self.dragEndPos)
        elif self.isPanning:
            tooltipText = "Panning"
            tooltipText += "\n" + str(self.panStartPos)
        elif self.isLinking:
            qp.setBrush(QBrush(QColor(100, 10, 10, 40)))
            qp.drawLine(self.linkSource.mapTo(self,self.linkSource.rect().center()), self.panEndPos)
            tooltipText = "Linking - Release over a destination node or combo box"
            tooltipText += "\n" + str(self.linkSource)
        else:
            if self.hover == HoveringOver.BACKGROUND:
                tooltipText = "Left mouse - Select"
                tooltipText += "\nRight mouse - Pan view"
            elif self.hover == HoveringOver.GRAPH_NODE:
                tooltipText = "Left mouse - Select / Move node"
            elif self.hover == HoveringOver.VAR_LINK_BUTTON:
                tooltipText = "Left mouse - Toggle variable link info"
                tooltipText += "\nRight mouse - Quick link"
            elif self.hover == HoveringOver.OUT_LINK_BUTTON:
                tooltipText = "Left mouse - Toggle output link info"
                tooltipText += "\nRight mouse - Quick link"
            elif self.hover is not HoveringOver.UNKNOWN:
                tooltipText = "Left mouse - Show dropdown options"
                tooltipText += "\nRight mouse - Quick link"
        self.tooltipLabel.setText(tooltipText)
        self.tooltipLabel.adjustSize()
        self.tooltipLabel.move(10,10)
        self.tooltipLabel.raise_()
    
    
    def mousePressEvent(self, event):
        if not self.dragObject:
            if event.button() == _SECONDARY_BUTTON:
                self.isPanning=True
                self.panStartPos = event.pos()
                self.update()
            elif event.button() == _PRIMARY_BUTTON:
                self.isSelecting=True
                self.selectStartPos = event.pos()
                self.selectEndPos = None
    
    def mouseMoveEvent(self, event):   
        if event.buttons() == _SECONDARY_BUTTON:
            if self.isPanning:
                self.panEndPos = event.pos()
                self.scroll(self.panEndPos.x()-self.panStartPos.x(), self.panEndPos.y()-self.panStartPos.y())
                self.panStartPos=self.panEndPos
                self.update()
            elif self.isLinking:
                self.panEndPos = event.pos()
                self.update()
            return
        
        if event.buttons() == _PRIMARY_BUTTON:
            if self.isSelecting:
                self.selectEndPos = event.pos()
                self.update()
            if self.isDragging:
                if (event.pos().x()>0 and event.pos().y()>0 and event.pos().x()<self.width() and event.pos().y()<self.height()):
                    self.dragEndPos = event.pos()
                    self.update()
            elif self.dragObject and ((event.pos() - self.dragStartPos).manhattanLength() >= QApplication.startDragDistance()):
                self.isDragging = True
    
    def mouseReleaseEvent(self, event):
        if event.button() == _PRIMARY_BUTTON:
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
                        if selectangle.contains(node.geometry()):
                            node.Select()
                    self.setStyleSheet(self.styleSheet())
                            
        
        if event.button() == _SECONDARY_BUTTON:
            self.isDragging=False
            self.isPanning=False
            self.panStartPos=None
            if self.isLinking:
                dest = self.childAt(event.pos())
                if dest is not None:
                    while not issubclass(type(dest),Hoverable) and dest is not self:
                        dest = dest.parentWidget()
                    if dest is not self:
                        dest.GetGraphNode().seqGraph.QuickLink(self.linkSource, dest)
            
        self.isSelecting=False
        self.isLinking=False
        self.dragObject=None
        self.update()


class SequenceGraph():
    """A single BPD sequence's node tree"""
    def __init__(self, canvas:GraphCanvas, sequence:BehaviorSequence):
        self.canvas = canvas
        self.sequence = sequence
        
        self.rootNode:GraphNode
        self.varNode:VarsNode
        self.sequenceNodes = []
        
    def MakeNodes(self):
        """
        Create the GraphNodes for this BehaviorSequence data
        """
        self.rootNode = GraphNode("SEQUENCE ROOT", self, self.canvas)
        self.rootNode.setFixedSize(0,0)
        
        # First make a fake connection to this sequence's Variables node so it's on the left of the rest
        self.varNode = VarsNode(self.sequence.VariableData, self, self.canvas)
        self.rootNode.outConnections.append(Connection(self.rootNode, -1, self.varNode, -1))
        
        for event in self.sequence.EventData2:
            node = EventNode(event, self, self.canvas)
            self.rootNode.outConnections.append(Connection(self.rootNode,-1,node,-1))
        for beh in self.sequence.BehaviorData2:
            node = BehaviorNode(beh, self, self.canvas)
    
        self.MakeConnections()
        
        # Find "orphan" nodes that have no input connections and make fake connections
        for node in self.sequenceNodes:
            if len(node.inConnections) == 0:
                self.rootNode.outConnections.append(Connection(self.rootNode, -1, node, -1))
    
    def MakeConnections(self):
        """
        Create the connections between this sequence's GraphNodes
        Called once all nodes have been created
        """
        Connections = []
        for child in self.sequenceNodes:
            for idx,con in enumerate(child.data.Outputs):
                dest = self.FindNode(con.LinkedBehavior)
                conny = Connection(child,idx,dest,-1)
                Connections.append(conny)
                child.outConnections.append(conny)
            
            for idx, link in enumerate(child.data.Variables):
                for varIdx in link.LinkedVariableIndexes:
                    if varIdx >= 0: # Might be blank if this variable was removed
                        child.varListConnections.append(Connection(child,idx,self.varNode,varIdx))
                        if link.VariableLinkType == VariableLinkTypes.BVARLINK_Output:
                            # Is this variable used in another node?
                            for node in self.sequenceNodes:
                                for idx2, link2 in enumerate(node.data.Variables):
                                    if link2.VariableLinkType != VariableLinkTypes.BVARLINK_Output:
                                        for varIdx2 in link2.LinkedVariableIndexes:
                                            if varIdx is varIdx2:
                                                child.varConnections.append(Connection(child,idx,node,idx2))
                                                break
            
    def FindNode(self, b:BehaviorData):
        """ Returns the node for the given BehaviorData object"""
        for child in self.sequenceNodes:
            if child.data is b:
                return child
    
    def NewEventNode(self):
        newData = EventData({
            'UserData':{
                'EventName':'\"NewEvent\"', 
                'bEnabled':'True', 
                'bReplicate':'False', 
                'MaxTriggerCount':'0', 
                'ReTriggerDelay':'0.000000', 
                'FilterObject':'None'  
            }, 
            'OutputVariables':{'ArrayIndexAndLength':'0'},
            'OutputLinks':{'ArrayIndexAndLength':'0'}
            }, self.sequence)
        self.sequence.EventData2.append(newData)
        node = EventNode(newData, self, self.canvas)
        node.move(self.canvas.rect().center())
        node.show()
        self.rootNode.outConnections.append(Connection(self.rootNode,-1,node,-1))
        self.canvas.parent().toolbar.action_new_event.setChecked(True)
        
    def NewBehaviorNode(self):
        newData = BehaviorData({
            'Behavior':'Behavior_NewClass\'NewBehaviorObject\'',
            'LinkedVariables':{'ArrayIndexAndLength':'0'},
            'OutputLinks':{'ArrayIndexAndLength':'0'}
            }, self.sequence)
        self.sequence.BehaviorData2.append(newData)
        node = BehaviorNode(newData, self, self.canvas)
        node.move(self.canvas.rect().center())
        node.show()
        self.rootNode.outConnections.append(Connection(self.rootNode,-1,node,-1))
        # Also update all the combo boxes for output links
        for node in self.sequenceNodes:
            for item in node.outLinkList.items:
                dropdown = item.dropdown
                i = dropdown.count()-1
                dropdown.addItem(f"{str(i)} - {str(newData.BehaviorObject.split('.')[-1])}")
        self.canvas.parent().toolbar.action_new_behavior.setChecked(True)    

    def QuickLink(self, source:QWidget, event):
            """
            Link to this specific variable link / output / variable
                From node to node
                  Sequence to Sequence - new output link
                  Sequence to VarNode - new variable link
                From combo to node
                  Out combo to Sequence - change output link
                  Var combo to VarNode - change var link to new variable
                From node to combo
                  Sequence to VarNode combo - new var link to specific var
                  Sequence to Sequence VarLink combo - new var link to specific var
                From combo to combo
                  VarLink combo to VarNode combo - change var link to specific var
                  VarNode combo to VarLink combo - change var link to specific var
                  VarLink combo to VarLink combo - output var from source to input var in dest
            """
            if not source or not event:
                return
            dest = self.canvas.childAt(source.mapTo(self.canvas,event.pos()))
            if dest is None:
                #QMessageBox.information(self.canvas, 'Whoops', "No link destination!")
                return
            
            while type(source) is not NodeCombo and not issubclass(type(source),GraphNode):
                source = source.parentWidget()
                if source is None or source is self:
                    return
            while type(dest) is not NodeCombo and not issubclass(type(dest),GraphNode):
                dest = dest.parentWidget()
                if dest is None or dest is self:
                    return
                
            # Check we're linking within the same BehaviorSequence
            sourceNode = source
            while not issubclass(type(sourceNode),GraphNode) and sourceNode is not self: sourceNode = sourceNode.parentWidget()
            destNode = dest
            while not issubclass(type(destNode),GraphNode) and destNode is not self: destNode = destNode.parentWidget()
            if not (sourceNode.seqGraph is self and destNode.seqGraph is self):
                QMessageBox.information(self.canvas, 'Whoops', "Can't link across separate BehaviorSequences!")
                return
            
            if type(dest) is BehaviorNode and issubclass(type(source),SequenceNode):
                # New output link
                index = self.sequence.BehaviorData2.index(dest.data)
                source.outLinkList.NewRow()
                source.outLinkList.items[-1].dropdown.setCurrentIndex(index)
            elif type(dest) is VarsNode and issubclass(type(source),SequenceNode):
                # New variable link to a new variable
                dest.NewVariable()
                index = len(dest.items)-1
                source.varLinkList.NewRow()
                source.varLinkList.items[-1].varDropdownList[0].setCurrentIndex(index)
                
            elif issubclass(type(dest),GraphNode) and type(source) is NodeCombo:
                # From combo to node
                if source.enterHover is HoveringOver.OUT_LINK_COMBO and type(dest) is BehaviorNode:
                    index = self.sequence.BehaviorData2.index(dest.data)
                    source.setCurrentIndex(index)
                elif source.enterHover is HoveringOver.VAR_LINK_COMBO and type(dest) is VarsNode:
                    dest.NewVariable()
                    index = len(dest.items)-1
                    source.setCurrentIndex(index)
                    
            elif type(dest) is NodeCombo and issubclass(type(source),SequenceNode):
                # From node to combo
                if dest.enterHover is HoveringOver.VAR_NODE_COMBO:
                    for i, item in enumerate(self.varNode.items):
                        if item[2] is dest:
                            index = i
                            break
                    source.varLinkList.NewRow()
                    source.varLinkList.items[-1].varDropdownList[0].setCurrentIndex(index)
                elif dest.enterHover is HoveringOver.VAR_LINK_COMBO:
                    source.varLinkList.NewRow()
                    source.varLinkList.items[-1].varDropdownList[0].setCurrentIndex(dest.currentIndex())
                source.varLinkList.AttChanged()
                    
            elif type(dest) is NodeCombo and type(source) is NodeCombo:
                # From combo to combo
                if source.enterHover is HoveringOver.VAR_LINK_COMBO and dest.enterHover is HoveringOver.VAR_NODE_COMBO:
                    for i, item in enumerate(self.varNode.items):
                        if item.dropdown is dest:
                            index = i
                            break
                    source.setCurrentIndex(index)
                elif source.enterHover is HoveringOver.VAR_NODE_COMBO and dest.enterHover is HoveringOver.VAR_LINK_COMBO:
                    for i, item in enumerate(self.varNode.items):
                        if item.dropdown is source:
                            index = i
                            break
                    dest.setCurrentIndex(index)
                elif source.enterHover is HoveringOver.VAR_LINK_COMBO and dest.enterHover is HoveringOver.VAR_LINK_COMBO:
                    dest.setCurrentIndex(source.currentIndex())
                    for item in sourceNode.varLinkList.items:
                        if item.varDropdownList[0] is source:
                            item.dropdown.setCurrentIndex(VariableLinkTypes.BVARLINK_Output.value)
                            break
                    for item in destNode.varLinkList.items:
                        if item.varDropdownList[0] is dest:
                            item.dropdown.setCurrentIndex(VariableLinkTypes.BVARLINK_Input.value)
                            break

"""
Abstract Node Classes
Mostly to handle user inputs on all nodes
"""
class GraphNode(QGroupBox):
    """ Base Node class """
    def __init__(self, title, seqGraph, parent):
        super().__init__(title, parent)
        self.seqGraph:SequenceGraph = seqGraph
        self.canvas:GraphCanvas = parent
        self.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding)
        """ To filter to the correct sequence for links """

        self.inConnections=[]
        """ Connections from other nodes - automatically added when a Connection in initialised """
        self.outConnections=[]
        """ Connections from this node's output links """
        self.varConnections=[]
        """ Connections to other node that gives an output to a variable we input """
        self.varListConnections=[]
        """ Connections to the variable list node """
        self.hasBeenPositioned:bool = False
        self.isSelected:bool = False
        
    def Select(self):
        if self not in self.canvas.selectedNodes:
            self.isSelected=True
            self.canvas.selectedNodes.append(self)
            self.canvas.lastSelectedSequenceGraph = self.seqGraph
            if issubclass(type(self), SequenceNode):
                self.canvas.parent().toolbar.action_delete.setCheckable(True)
                self.canvas.parent().toolbar.action_delete.setChecked(True)
            self.setProperty("selected","true")
    
    
    def mousePressEvent(self, event):
        self.raise_()
        self.adjustSize()
        if event.button() == _PRIMARY_BUTTON and not self.canvas.isLinking:
            self.canvas.dragObject=self
            self.canvas.dragObjectPos = event.pos()
            self.canvas.dragStartPos = event.pos()+self.pos()
            if self not in self.canvas.selectedNodes:
                self.canvas.ClearSelection()
                self.Select()
                self.canvas.setStyleSheet(self.canvas.styleSheet())
        
    def mouseReleaseEvent(self, event):
        self.adjustSize()
        if event.button() == _SECONDARY_BUTTON and self.canvas.isLinking:
            self.canvas.isLinking=False
            self.canvas.linkDest=self
            self.seqGraph.QuickLink(self.canvas.linkSource, event)
            self.canvas.update()
        else:
            super().mouseReleaseEvent(event)
                    
                
    def enterEvent(self, event):
        self.canvas.hover = HoveringOver.GRAPH_NODE
        self.canvas.update()
    def leaveEvent(self, event):
        self.canvas.hover = HoveringOver.BACKGROUND
        self.canvas.update()


class Hoverable():
    """ Has events to track what is being hovered over for the tooltips, and quick links """
        
    def SetHover(self, enterHover:HoveringOver = HoveringOver.UNKNOWN, leaveHover:HoveringOver = HoveringOver.UNKNOWN):
        self.enterHover:HoveringOver = enterHover
        self.leaveHover:HoveringOver = leaveHover
    
    def GetCanvas(self) -> GraphCanvas:
        canvas = self.parentWidget()
        while type(canvas) is not GraphCanvas: canvas = canvas.parentWidget()   # Yeah...
        return canvas
    
    def GetGraphNode(self) -> GraphNode:
        node = self
        while not issubclass(type(node),GraphNode): node = node.parentWidget()   # Yeah...
        return node
    
    def mousePressEvent_(self, event):
        self.parentWidget().raise_()
        canvas = self.GetCanvas()
        if event.button() == _SECONDARY_BUTTON and not canvas.isLinking:
            canvas.isLinking=True
            canvas.linkSource=self
            
    def mouseReleaseEvent_(self, event):
        self.parentWidget().update()
        self.parentWidget().adjustSize()
        canvas = self.GetCanvas()
        if event.button() == _SECONDARY_BUTTON and canvas.isLinking:
            canvas.isLinking=False
            self.GetGraphNode().seqGraph.QuickLink(canvas.linkSource, event)
    
    def enterEvent(self, event):
        canvas = self.GetCanvas()
        if canvas:
            canvas.hover=self.enterHover
            canvas.update()
    def leaveEvent(self, event):
        canvas = self.GetCanvas()
        if canvas:
            canvas.hover=self.leaveHover
            canvas.update()


class NodeButton(QPushButton, Hoverable):
    """ Just a QPushButton, but has multiple inheritance to send link events and update our tooltips """
    def mousePressEvent(self, event):
        super().mousePressEvent(event)
        self.mousePressEvent_(event)
    
    def mouseReleaseEvent(self, event):
        super().mouseReleaseEvent(event)
        self.mouseReleaseEvent_(event)


class NodeCombo(QComboBox, Hoverable):
    """ Just a QComboBox, but has multiple inheritance to send link events and update our tooltips """
    def mousePressEvent(self, event):
        super().mousePressEvent(event)
        self.mousePressEvent_(event)
    
    def mouseReleaseEvent(self, event):
        super().mouseReleaseEvent(event)
        self.mouseReleaseEvent_(event)


class Connection():
    def __init__(self, sourceNode:GraphNode, sourceIndex, destNode:GraphNode, destIndex) -> None:
        self.sourceNode:GraphNode = sourceNode
        self.sourceIndex:int = sourceIndex
        self.destNode:GraphNode = destNode
        self.destIndex:int = destIndex
        
        destNode.inConnections.append(self)

    def Remove(self) -> None:
        if self in self.destNode.inConnections:
            self.destNode.inConnections.remove(self)
        if self in self.sourceNode.outConnections:
            self.sourceNode.outConnections.remove(self)
        if self in self.sourceNode.varConnections:
            self.sourceNode.varConnections.remove(self)
        if self in self.sourceNode.varListConnections:
            self.sourceNode.varListConnections.remove(self)
        del self


"""
BPD Specific Node Classes
"""
class SequenceNode(GraphNode):
    """ Base node for Events and Behaviors - having Output Links and Variable Links """
    def __init__(self, title, data, seqGraph, parent):
        super().__init__(title, seqGraph, parent)
        if seqGraph:
            seqGraph.sequenceNodes.append(self)
        self.data = data
        
        self.varLinkList:VarLinksList = VarLinksList(self, data.Variables)
        self.outLinkList:OutputLinksList = OutputLinksList(self, data.Outputs)
        self.varLinkButton = NodeButton("Variables")
        self.varLinkButton.SetHover(HoveringOver.VAR_LINK_BUTTON, HoveringOver.GRAPH_NODE)
        self.varLinkButton.clicked.connect(self.VarLinkToggle)
        self.outLinkButton = NodeButton("Output Links")
        self.outLinkButton.SetHover(HoveringOver.OUT_LINK_BUTTON, HoveringOver.GRAPH_NODE)
        self.outLinkButton.clicked.connect(self.OutLinkToggle)
        self.varLinkButton.rect().left
        
        layout= QVBoxLayout(self)
        self.nodeLayout = QGridLayout()
        """ The inner QLayout for this node's custom widgets """
        layout.addLayout(self.nodeLayout)
        layout.addWidget(self.varLinkButton)
        layout.addWidget(self.varLinkList)
        layout.addWidget(self.outLinkButton)
        layout.addWidget(self.outLinkList)
        
    def VarLinkToggle(self):
        if self.varLinkList.isVisible():
            self.varLinkList.hide()
        else:
            self.varLinkList.show()
        self.seqGraph.canvas.update()
        # Reposition to keep centered
        oldCentre = self.rect().center()
        self.adjustSize()
        newCentre = self.rect().center()
        self.move(self.pos().x() + (oldCentre - newCentre).x(), self.pos().y())
        
    def OutLinkToggle(self):
        if self.outLinkList.isVisible():
            self.outLinkList.hide()
        else:
            self.outLinkList.show()
        self.seqGraph.canvas.update()
        # Reposition to keep centered
        oldCentre = self.rect().center()
        self.adjustSize()
        newCentre = self.rect().center()
        self.move(self.pos().x() + (oldCentre - newCentre).x(), self.pos().y())

    def Delete(self):
        """
        Delete this node, its connections, and its data from the sequence.
        """
        seq = self.seqGraph.sequence
        if self.data in seq.BehaviorData2:
            # Also remove update all the combo boxes for output links - careful with the new indexes
            idx = seq.BehaviorData2.index(self.data)
            seq.BehaviorData2.remove(self.data)
            for node in self.seqGraph.sequenceNodes:
                outLinkList = node.outLinkList
                for item in outLinkList.items:
                    dropdown = item.dropdown
                    if dropdown.currentIndex() == idx:
                        dropdown.setCurrentIndex(-1)
                    dropdown.removeItem(idx)
                    # We don't want to just clear and add the updated list, because that reset the combo box indexes
                    for i in range(idx, dropdown.count()-1):
                        dropdown.setItemText(i,f"{str(i)} - {str(seq.BehaviorData2[i].BehaviorObject.split('.')[-1])}")     
            
        if self.data in seq.EventData2:
            seq.EventData2.remove(self.data)
            
        for con in reversed(self.inConnections): con.Remove()
        for con in reversed(self.outConnections): con.Remove()
        for con in reversed(self.varConnections): con.Remove()
        for con in reversed(self.varListConnections): con.Remove()

        self.seqGraph.sequenceNodes.remove(self)
        
        self.deleteLater()


class EventNode(SequenceNode):
    def __init__(self, data:EventData, seqID, parent):
        super().__init__("Event", data, seqID, parent)
        
        self.userDataList = DictionaryList(self, data.UserData)
        self.eventNameBox:QLineEdit = self.userDataList.items[0][1]
        completer=QCompleter(eventDict.keys(), self)
        completer.setCaseSensitivity(Qt.CaseInsensitive)
        self.eventNameBox.setCompleter(completer)
        self.eventNameBox.editingFinished.connect(self.EventNameChanged)
        self.messageBoxShown = False
        self.nodeLayout.addWidget(self.userDataList)
        
    def EventNameChanged(self):
        """ Offer to replace the variable links if the new name is found in our known dictionary """
        if self.messageBoxShown:   # Bug where the editingFinished signal fires twice or something
            return
        
        newName = self.eventNameBox.text()
        if newName in eventDictFull:
            eventLinks = eventDictFull[newName]['OutputVariablesByConnectionIndex']
            if len(eventLinks.items()) == 0:
                return
            
            self.messageBoxShown = True
            linkList = [f"{k} - {v['PropertyName'][0]} - {v['VariableLinkType'][0]}" for k,v in sorted(eventLinks.items())]
            ret = QMessageBox.question(self,'Replace Links', "This event name has been found with variable links in the data.\
                <p>Do you want to replace the variable links with the following?<br>"+'<br>'.join(linkList), QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if ret == QMessageBox.Yes:
                # Clear all existing var links
                while len(self.varLinkList.items)>0: self.varLinkList.RemoveRow()
                # Add in the new var links from the dictionary
                for k,v in sorted(eventLinks.items()):
                    self.varLinkList.NewRow()
                    varLinkItem = self.varLinkList.items[-1]
                    varLinkItem.idBox.setText(k)
                    varLinkItem.nameBox.setText(v['PropertyName'][0])
                    varLinkItem.dropdown.setCurrentIndex(VariableLinkTypes[v['VariableLinkType'][0]].value)
                self.varLinkList.AttChanged()
        self.messageBoxShown=False
        self.sender().clearFocus()


class BehaviorNode(SequenceNode):
    def __init__(self, data:BehaviorData, seqGraph, parent):
        super().__init__("Behavior", data, seqGraph, parent)
       
        l0=QLabel("Class")
        self.p0=QLineEdit(self.data.BehaviorClass)
        completer=QCompleter(behaviorDict.keys(), self)
        completer.setCaseSensitivity(Qt.CaseInsensitive)
        self.p0.setCompleter(completer)
        self.p0.editingFinished.connect(self.BehaviorClassChanged)
        self.p0.textChanged.connect(self.AttChanged)
        self.messageBoxShown = False
        l1=QLabel("Object")
        self.p1=QLineEdit(self.data.BehaviorObject)
        self.p1.textChanged.connect(self.AttChanged)
        
        layout = self.nodeLayout
        layout.addWidget(l0,0,0)
        layout.addWidget(self.p0,0,1)
        layout.addWidget(l1,1,0)
        layout.addWidget(self.p1,2,0,1,2)
        
    def BehaviorClassChanged(self):
        """ Offer to replace the variable links if the new name is found in our known dictionary """
        if self.messageBoxShown:   # Bug where the editingFinished signal fires twice or something
            return
        
        newName = self.p0.text()
        if newName in behaviorDict:
            behLinks = behaviorDict[newName]['LinkedVariablesByPropertyName']
            if len(behLinks.items()) == 0:
                return
            
            self.messageBoxShown = True
            linkList = [f"{v['ConnectionIndex'][0]} - {k} - {v['VariableLinkType'][0]} - {v['ArrayIndexFromBehavior'][0]}" for k,v in behLinks.items()]
            ret = QMessageBox.question(self,'Replace Links', "This behavior class has been found with variable links in the data.\
                <p>Do you want to replace the variable links with the following?<br>"+'<br>'.join(linkList), QMessageBox.Yes | QMessageBox.No,  QMessageBox.No)
            if ret == QMessageBox.Yes:
                # Clear all existing var links
                # This crashes if you click onto an item in the varLinkList to trigger this signal. And that's just fine by me.
                while len(self.varLinkList.items)>0: self.varLinkList.RemoveRow()
                # Add in the new var links from the dictionary
                for k,v in behLinks.items():
                    self.varLinkList.NewRow()
                    varLinkItem = self.varLinkList.items[-1]
                    varLinkItem.idBox.setText(str(v['ConnectionIndex'][0]))
                    varLinkItem.nameBox.setText(k)
                    varLinkItem.dropdown.setCurrentIndex(VariableLinkTypes[v['VariableLinkType'][0]].value)
                self.varLinkList.AttChanged()
        self.messageBoxShown=False
        self.sender().clearFocus()

    def AttChanged(self):
        """ Any one of this node's attributes has changed so update the data """
        self.data.BehaviorClass=self.p0.text()
        self.data.BehaviorObject=self.p1.text()
        self.data.Behavior=f"{self.data.BehaviorClass}\'{self.data.BehaviorObject}\'"
        # Update all the combo boxes on all nodes..............
        for node in self.seqGraph.sequenceNodes:
            outLinkList = node.outLinkList
            for item in outLinkList.items:
                dropdown = item.dropdown
                # We don't want to just clear and add the updated list, because that reset the combo box indexes
                for idx, b in enumerate(self.seqGraph.sequence.BehaviorData2):
                    dropdown.setItemText(idx,f"{str(idx)} - {str(b.BehaviorObject.split('.')[-1])}" )


class DictionaryList(QFrame):
    """ The widget list for extra node data. """
    def __init__(self, parent:SequenceNode, dataDict:dict):
        super().__init__(parent)
        self.parentNode:SequenceNode = parent
        self.sequenceData = parent.seqGraph.sequence
        self.data:dict = dataDict
        
        layout = self.parentNode.nodeLayout
        self.items=[]
        # Add a label and textbox/checkbox for each dictionary key/value pair
        for i, (key, value) in enumerate(self.data.items()):
            if key == 'FilterObject':
                continue    #  Don't care about this one
            
            label = QLabel(key)
            layout.addWidget(label,i,0)
            if value == 'True' or value == 'False':
                # Bools are a checkbox
                item = QCheckBox()
                item.setCheckState(Qt.CheckState.Checked if value == 'True' else Qt.CheckState.Unchecked)
                item.stateChanged.connect(self.AttChanged)
            else:
                # Anything else is a textbox
                item = QLineEdit(value.strip('"'))
                item.isStringType = item.text() != value
                item.textChanged.connect(self.AttChanged)
            layout.addWidget(item,i,1)
            self.items.append((label,item))
    
    def AttChanged(self):
        """
        Updates the data dictionary for the current fields
        """
        for (label,item) in self.items:
            if type(item) is QCheckBox:
                self.data[label.text()] = 'True' if item.isChecked() else 'False'
            else:
                if item.isStringType:
                    self.data[label.text()] = f'\"{item.text()}\"'
                else:
                    self.data[label.text()] = item.text()


class VarLinksList(QFrame):
    """ The expandable widget list for each variable link. """
    def __init__(self, parent:SequenceNode, variables:List[VariableLinkData]):
        super().__init__(parent)
        self.parentNode=parent
        self.sequenceData = self.parentNode.seqGraph.sequence
        self.linkData:List[VariableLinkData] = variables
        
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.hide()
        layout = QGridLayout(self)
        # Headers
        layout.addWidget(QLabel("Property Name"),0,0)
        layout.addWidget(QLabel("Link Type"),0,1)
        layout.addWidget(QLabel("Connection Index"),0,2)
        helpButton = QPushButton("?")
        helpButton.clicked.connect(self.HelpVariables)
        layout.addWidget(helpButton,0,3,Qt.AlignmentFlag.AlignTrailing)
        # New Button
        self.newButton = QPushButton("+")
        self.newButton.clicked.connect(self.NewRow)
        layout.addWidget(self.newButton,layout.rowCount()+1,0,1,3)
        self.items:List[VarLinkItem] = []
        for link in self.linkData:
            self.AddRow(layout,link)
    
    def AddRow(self, layout:QGridLayout, link:VariableLinkData):
        newItem = VarLinkItem(self,link)
        self.items.append(newItem)

        i = layout.rowCount()-1
        layout.addWidget(newItem.nameBox,i,0)
        layout.addWidget(newItem.dropdown,i,1)
        layout.addWidget(newItem.idBox,i,2)
        layout.addWidget(newItem.removeButton,i,3,2,1,Qt.AlignmentFlag.AlignTrailing)

        for varDropdown in newItem.varDropdownList:
            i = i + 1
            layout.addWidget(varDropdown,i,0,1,3)

        layout.addWidget(self.newButton,i+1,0,1,3)
    
    def AttChanged(self):
        """
        Update the VariableLinkData for all var links on this node, and update var connections
        This does NOT update the BehaviorData/EventData LinkedVariables - that happens when we reconsolidate everything!
        """
        # Reverse as we're editing a list that we're iterating over...
        for con in reversed(self.parentNode.inConnections):
            if con.destIndex >=0: # I.E. if a var connection - bodge
                con.Remove()
        for con in reversed(self.parentNode.varConnections):
            if con.destIndex >=0: # I.E. if a var connection - bodge
                con.Remove()
        
        for idx, row in enumerate(self.items):
            link = row.link
            link.PropertyName = row.nameBox.text()
            link.VariableLinkType = VariableLinkTypes(row.dropdown.currentIndex())
            try:
                link.ConnectionIndex = int(row.idBox.text())
            except: # Not an integer
                link.ConnectionIndex = link.ConnectionIndex
            
            for listIdx,varDropdown in enumerate(row.varDropdownList):
                while listIdx >= len(link.LinkedVariableIndexes):   # If we've added a blank variable with IndexAndLength=0
                    link.LinkedVariableIndexes.append(-1)
                    
                varIdx = varDropdown.currentIndex()
                link.LinkedVariableIndexes[listIdx] = varIdx
                if varIdx >= 0: # Might be blank if this variable was removed
                    # And update the connections to point to the right var item in the vars node
                    self.parentNode.varListConnections[idx] = Connection(self.parentNode,idx,self.parentNode.seqGraph.varNode,varIdx)
                    # Also don't forget this connection fun...
                    if link.VariableLinkType == VariableLinkTypes.BVARLINK_Output:
                        # Is this variable used in another node?
                        for node in self.parentNode.seqGraph.sequenceNodes:
                            for idx2, link2 in enumerate(node.data.Variables):
                                if link2.VariableLinkType != VariableLinkTypes.BVARLINK_Output:
                                    for varIdx2 in link2.LinkedVariableIndexes:
                                        if varIdx is varIdx2:
                                            self.parentNode.varConnections.append(Connection(self.parentNode,idx,node,idx2))
                                            break
                                            
                    else:
                        # Is this variable set from another node?
                        for node in self.parentNode.seqGraph.sequenceNodes:
                            for idx2, link2 in enumerate(node.data.Variables):
                                if link2.VariableLinkType == VariableLinkTypes.BVARLINK_Output:
                                    for varIdx2 in link2.LinkedVariableIndexes:
                                        if varIdx is varIdx2:
                                            node.varConnections.append(Connection(node,idx2, self.parentNode,idx))
                                            break
                    
        self.parentNode.seqGraph.canvas.update()
    
    def NewRow(self):
        linkType = 'BVARLINK_Unknown' if type(self.parentNode) is not EventNode else 'BVARLINK_Output'
        cId = 0 if type(self.parentNode) is not EventNode else len(self.linkData)
        link = VariableLinkData({'PropertyName':'NewVarLink','VariableLinkType':linkType,'ConnectionIndex':str(cId),'LinkedVariables':{'ArrayIndexAndLength':'0'},'CachedProperty':'None'}, self.sequenceData)
        self.parentNode.varListConnections.append(Connection(self.parentNode,len(self.linkData),self.parentNode.seqGraph.varNode,-1))
        self.linkData.append(link)
        self.sequenceData.ConsolidatedVariableLinkData.append(link)
        
        self.AddRow(self.layout(),link)
        self.parentNode.adjustSize()
        self.parentNode.seqGraph.canvas.update()
    
    def RemoveRow(self):
        for idx,row in enumerate(self.items):
            # If this wasn't sent from a button then just remove the first row
            if type(self.sender()) is not QPushButton or row.removeButton is self.sender():
                self.items.remove(row)
                self.parentNode.varListConnections[idx].Remove()
                self.sequenceData.ConsolidatedVariableLinkData.remove(self.linkData[idx])
                del self.linkData[idx]
                # Reversed cus changing list we're iterating over
                for con in reversed(self.parentNode.inConnections+self.parentNode.varConnections):
                    if con.sourceIndex == idx:
                        con.Remove()

                # NOTE this isn't actually removing the row from the grid layout but IDC
                for dropDown in row.varDropdownList:
                    self.layout().removeWidget(dropDown)
                self.layout().removeWidget(row.nameBox)
                self.layout().removeWidget(row.dropdown)
                self.layout().removeWidget(row.idBox)
                self.layout().removeWidget(row.removeButton)
                self.layout().removeWidget(row.removeButton)  # Remove twice cus spans two grid positions
                self.parentNode.adjustSize()
                self.parentNode.seqGraph.canvas.update()
                return

    def HelpVariables(self):
        QMessageBox.information(self, 'Help', "Wiki Help: <a href='https://github.com/BLCM/BLCMods/wiki/BPD-classroom' style='color:orange'>BLCMods BPD Classroom</a>"\
            "<p>Variable Links are specific for each Event and Behavior type. They are defined in the game code. Not all available variables need to be linked, but those that are need to use the correct Link Type and info:"\
            "<br>For Events, it seems like only the Connection Indexes need to match."\
            "<br>For Behaviors, it seems like only the Property Names need to match."\
            "<br><p>Where do the Variable Links come from?"\
            "<p>Look inside WillowGame.upk, GearboxFramework.upk or Engine.upk,"\
            " using <a href='https://github.com/BLCM/BLCMods/wiki#modders-tools' style='color:orange'>UE Explorer</a>."\
            "<br>This editor also has json files containing all unique link properties found in the data, which will be suggested if any are found. But this is not an exhaustive list."\
            "<p>For Events, find the method with the name of the event in the parent class of the BPD."\
            " For example, ShieldDefinition has OnAmmoAbsorbed(), with variable links [Object ShieldOwner, Object DamageSource, Object DamageType]."\
            "<p>For Behaviors, see the class attributes in the UnrealScript for this behavior class. For variable ouputs, see the PublishBehaviorOutput() method."\
            )

class VarLinkItem():
    """ A group of widgets representing a single VariableLinkData """
    def __init__(self, parent:VarLinksList, link:VariableLinkData):
        self.link = link
        self.nameBox = QLineEdit(str(link.PropertyName))
        self.nameBox.textEdited.connect(parent.AttChanged)
        self.dropdown = QComboBox()
        self.dropdown.addItems(VariableLinkTypes._member_names_[0:VariableLinkTypes.BVARLINK_MAX.value])
        self.dropdown.setCurrentIndex(link.VariableLinkType.value)
        self.dropdown.currentIndexChanged.connect(parent.AttChanged)
        self.idBox = QLineEdit(str(link.ConnectionIndex))
        self.idBox.textEdited.connect(parent.AttChanged)
        self.removeButton=QPushButton("-")
        self.removeButton.clicked.connect(parent.RemoveRow)
        
        # Add multiple combo-boxes populated with the vars list from that node
        self.varDropdownList=[]
        if len(link.LinkedVariableList)>0:
            for idx, var in enumerate(link.LinkedVariableList):
                varDropdown = NodeCombo()
                varDropdown.SetHover(HoveringOver.VAR_LINK_COMBO, HoveringOver.GRAPH_NODE)
                varDropdown.addItems(f"{str(i)} - {v.Name} - {str(v.Type.name)}" for i,v in enumerate(link.sequence.VariableData))
                varDropdown.setCurrentIndex(idx + link.sequence.ConsolidatedLinkedVariables[parse_arrayindexandlength(link.LinkedVariables)[0]])
                varDropdown.currentIndexChanged.connect(parent.AttChanged)
                self.varDropdownList.append(varDropdown)
        else:
            # Still add a blank
            varDropdown = NodeCombo()
            varDropdown.SetHover(HoveringOver.VAR_LINK_COMBO, HoveringOver.GRAPH_NODE)
            varDropdown.addItems(f"{str(i)} - {varItem.textbox.text()} - {str(varItem.dropdown.currentText())}" for i, varItem in enumerate(parent.parentNode.seqGraph.varNode.items))
            varDropdown.currentIndexChanged.connect(parent.AttChanged)
            self.varDropdownList.append(varDropdown)


class OutputLinksList(QFrame):
    """ The expandable widget list for each output link. """
    def __init__(self, parent:SequenceNode, outputs:List[OutputLinkData]):
        super().__init__(parent)
        self.parentNode:SequenceNode=parent
        self.sequenceData = self.parentNode.seqGraph.sequence
        self.linkData:List[OutputLinkData] = outputs
        
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.hide()
        layout = QGridLayout(self)
        # Headers
        layout.addWidget(QLabel("Link ID"),0,0)
        layout.addWidget(QLabel("Activate Delay"),0,1)
        helpButton = QPushButton("?")
        helpButton.clicked.connect(self.HelpOutputs)
        layout.addWidget(helpButton,0,2,Qt.AlignmentFlag.AlignTrailing)
        # New Button
        self.newButton = QPushButton("+")
        self.newButton.clicked.connect(self.NewRow)
        layout.addWidget(self.newButton,layout.rowCount()+1,0,1,2)
        self.items:List[OutputLinkItem] = []
        for link in self.linkData:
            self.AddRow(layout,link)
    
    def AddRow(self, layout:QGridLayout, link:OutputLinkData):
        newItem = OutputLinkItem(self, link)
        self.items.append(newItem)
        
        i = layout.rowCount()-1
        layout.addWidget(newItem.idBox,i,0)
        layout.addWidget(newItem.delayBox,i,1)
        layout.addWidget(newItem.removeButton,i,2,2,1,Qt.AlignmentFlag.AlignTrailing)
        layout.addWidget(newItem.dropdown,i+1,0,1,2)
        layout.addWidget(self.newButton,i+2,0,1,2)
    
    def AttChanged(self):
        """
        Update the OutputLinkData for all outputs on this node
        This does NOT update the BehaviorData/EventData OutputLinks - that happens when we reconsolidate everything!
        """
        # Reverse as we're editing a list that we're iterating over...
        for con in reversed(self.parentNode.outConnections):
            con.Remove()

        for idx, row in enumerate(self.items):
            link = row.link
            link.ActiveDelay = float(row.delayBox.text())
            try:
                link.LinkId = int(row.idBox.text())
            except: # Not an integer
                link.LinkId = link.LinkId
            link.LinkIndex = int(row.dropdown.currentIndex())
            if link.LinkIndex >=0:  # Might be blank if this behavior was removed
                # We now need to COMBINE the LinkID and LinkIndex, back into the LinkIdAndLinkedBehavior
                link.LinkIdAndLinkedBehavior=pack_linkidandlinkedbehavior(link.LinkId,link.LinkIndex)
                link.LinkedBehavior = link.sequence.BehaviorData2[link.LinkIndex]
                # And update the connections to point to the right behaviors
                dest = self.parentNode.seqGraph.FindNode(link.LinkedBehavior)
                self.parentNode.outConnections.append(Connection(self.parentNode,-1,dest,-1))
            else:
                link.LinkIdAndLinkedBehavior = -1
                link.LinkedBehavior = None
                # Bodge link to self because I CBA do these connections right
                self.parentNode.outConnections.append(Connection(self.parentNode,-1,self.parentNode,-1))
        self.parentNode.seqGraph.canvas.update()
    
    def NewRow(self):
        link = OutputLinkData({'LinkIdAndLinkedBehavior':'0','ActivateDelay':'0.0'}, self.sequenceData)
        self.parentNode.outConnections.append(Connection(self.parentNode,-1,self.parentNode.seqGraph.FindNode(link.LinkedBehavior),-1))
        self.linkData.append(link)
        
        self.AddRow(self.layout(),link)
        self.parentNode.adjustSize()
        self.parentNode.seqGraph.canvas.update()

    def RemoveRow(self):
        for idx,row in enumerate(self.items):
            if row.removeButton is self.sender():
                self.parentNode.outConnections[idx].Remove()
                self.linkData.remove(row.link)
                self.items.remove(row)
                # NOTE this isn't actually removing the row from the grid layout but IDC
                self.layout().removeWidget(row.dropdown)
                self.layout().removeWidget(row.idBox)
                self.layout().removeWidget(row.delayBox)
                self.layout().removeWidget(row.removeButton)
                self.parentNode.adjustSize()
                self.parentNode.seqGraph.canvas.update()
                return

    def HelpOutputs(self):
        QMessageBox.information(self, 'Help', "Wiki Help: <a href='https://github.com/BLCM/BLCMods/wiki/BPD-classroom' style='color:orange'>BLCMods BPD Classroom</a>"\
            "<p>NOTE: Some Behavior classes don't fire ANY output links, even if they are given here, unless the linkID is -1!"\
            "<br><p>What do?"\
            "<p>ActivateDelay is the time delay before this output fires."\
            "<p>LinkID is used on some behavior classes. This can be used to choose between output links - not firing them all."\
            "<br>Look in the behavior's UnrealScript class - they actually list the linkIDs with descriptions in the defaultproperties{} struct, and you can see where the ActivateBehaviorOutputLink() method is called in the code with a linkID."\
            "<br><br>Behavior_IntSwitchRange uses it to decide which output to fire."\
            "<br>Behavior_DamageSourceSwitch uses it to restrict damage types."\
            "<br>Behavior_TriggerDialogEvent uses it loop the behavior until the dialogue is finished... maybe?"\
            "<br>Some have a linkID of -1. ¯\\_(ツ)_/¯"\
            )
    
class OutputLinkItem:
    """ A group of widgets representing a single OutputLinkData """
    def __init__(self, parent:OutputLinksList, link:OutputLinkData):
        self.link:OutputLinkData = link
        self.idBox:QLineEdit
        self.delayBox:QLineEdit
        self.removeButton:QPushButton
        self.dropdown:NodeCombo
        
        self.idBox = QLineEdit(str(link.LinkId))
        self.idBox.textEdited.connect(parent.AttChanged)
        self.delayBox = QLineEdit(str(link.ActiveDelay))
        self.delayBox.textEdited.connect(parent.AttChanged)
        self.removeButton=QPushButton("-")
        self.removeButton.clicked.connect(parent.RemoveRow)
        self.dropdown = NodeCombo()
        self.dropdown.SetHover(HoveringOver.OUT_LINK_COMBO, HoveringOver.GRAPH_NODE)
        self.dropdown.addItems(f"{str(i)} - {str(b.BehaviorObject.split('.')[-1])}" for i, b in enumerate(link.sequence.BehaviorData2))
        self.dropdown.setCurrentIndex(link.LinkIndex)
        self.dropdown.currentIndexChanged.connect(parent.AttChanged)


class VarsNode(GraphNode):
    def __init__(self, varData, seqID, parent):
        super().__init__("Variables", seqID, parent)
        self.varData = varData
        self.sequenceData = self.seqGraph.sequence
        
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
        self.items:List[VarItem] = []
        for var in varData:
            self.AddRow(layout,var)
    
    def AddRow(self, layout:QGridLayout, var:VariableData):
        newItem = VarItem(self, var)
        self.items.append(newItem)
        
        i = layout.rowCount()-1
        layout.addWidget(newItem.textbox,i,0)
        layout.addWidget(newItem.dropdown,i,1)
        layout.addWidget(newItem.removeButton,i,2,Qt.AlignmentFlag.AlignTrailing)
        layout.addWidget(self.newButton,i+1,0,1,2)

    
    def AttChanged(self):
        """ Any one of this node's attributes has changed so update the data """
        for idx, item in enumerate(self.items):
            item.varData.Name = item.textbox.text()
            item.varData.Type = VariableTypes(item.dropdown.currentIndex())
        # Update all the combo boxes on all nodes.............. Why aren't these signals and sockets????
        for node in self.seqGraph.sequenceNodes:
            varLinkList = node.varLinkList
            for item in varLinkList.items:
                for dropdown in item.varDropdownList:
                    # We don't want to just clear and add the updated list, because that reset the combo box indexes
                    for idx, item in enumerate(self.items):
                        dropdown.setItemText(idx,f"{str(idx)} - {item.varData.Name} - {str(item.varData.Type.name)}")

    def NewVariable(self):
        var = VariableData({'Name':'NewVariable','Type':'BVAR_None'}, self.sequenceData)
        self.varData.append(var)
        # Update all the combo boxes on all nodes..............
        for node in self.seqGraph.sequenceNodes:
            varLinkList = node.varLinkList
            for item in varLinkList.items:
                for dropdown in item.varDropdownList:
                    dropdown.addItem(f"{str(len(self.varData)-1)} - {var.Name} - {str(var.Type.name)}")
        
        self.AddRow(self.layout(),var)
        self.adjustSize()
        
    def RemoveVariable(self):
        for idx,row in enumerate(self.items):
            if row.removeButton is self.sender():
                self.varData.remove(row.varData)
                self.items.remove(row)
                # Update all the combo boxes on all nodes..............
                for node in self.seqGraph.sequenceNodes:
                    varLinkList = node.varLinkList
                    for item in varLinkList.items:
                        for dropdown in item.varDropdownList:
                            if dropdown.currentIndex() == idx:
                                dropdown.setCurrentIndex(-1)
                            dropdown.removeItem(idx)
                # Now that all indexes have been updated, also update all varConnections
                for node in self.seqGraph.sequenceNodes:
                    node.varLinkList.AttChanged()   # Easy mode
                
                # NOTE this isn't actually removing the row from the grid layout but IDC
                self.layout().removeWidget(row.textbox)
                self.layout().removeWidget(row.dropdown)
                self.layout().removeWidget(row.removeButton)
                self.adjustSize()
                self.AttChanged()   # Updated the indexes in the combo box names for other items
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
    def __init__(self, parent:VarsNode, var:VariableData):
        self.varData = var
        self.textbox = QLineEdit(var.Name)
        self.textbox.setSizePolicy(QSizePolicy.Expanding,QSizePolicy.Expanding)
        self.textbox.editingFinished.connect(parent.AttChanged)
        self.dropdown = NodeCombo()
        self.dropdown.SetHover(HoveringOver.VAR_NODE_COMBO, HoveringOver.GRAPH_NODE)
        self.dropdown.addItems(VariableTypes._member_names_[0:VariableTypes.BVAR_MAX.value])
        self.dropdown.setCurrentIndex(var.Type.value)
        self.dropdown.currentIndexChanged.connect(parent.AttChanged)
        self.removeButton=QPushButton("-")
        self.removeButton.clicked.connect(parent.RemoveVariable)


"""
Window stuff
"""
class MainToolBar(QToolBar):
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
        
        # BPD dump import/export
        self.action_bpd_import = self.addAction('Import BPD', parent.import_bpd)
        self.action_bpd_import.setCheckable(True)
        self.action_bpd_import.setChecked(True)
        self.action_bpd_export = self.addAction('Export BPD', parent.export_bpd)
        self.action_bpd_export.setCheckable(True)
        self.action_bpd_export.setChecked(True)
        
        # Spacer, after which everything else will be right-aligned
        spacer_label = QLabel()
        spacer_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.addWidget(spacer_label)
        
        self.action_new_behavior = self.addAction('New Behavior', parent.graphFrame.NewBehaviorNode)
        self.action_new_behavior.setToolTip('Adds a Behavior to the last selected BehaviorSequence')
        self.action_new_behavior.setCheckable(True)
        self.action_new_behavior.setChecked(True)
        self.action_new_event = self.addAction('New Event', parent.graphFrame.NewEventNode)
        self.action_new_event.setToolTip('Adds an Event to the last selected BehaviorSequence')
        self.action_new_event.setCheckable(True)
        self.action_new_event.setChecked(True)
        self.action_delete = self.addAction('Delete Behavior/Event', parent.graphFrame.DeleteSelectedNodes)
        self.action_delete.setToolTip('Removes the selected Events and Behaviors from the BehaviorSequence')

class BPDWindow(QMainWindow):
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
        shortcut = QShortcut(QKeySequence(Qt.CTRL + Qt.Key_Q), self)
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
            self.graphFrame.linkPenColor=QColorConstants.Red
            self.graphFrame.linkPenColor=QColorConstants.Svg.orangered
            #self.graphFrame.linkPenColor=QColorConstants.Svg.darkorange
        else:
            self.app.setStyleSheet('')
            self.graphFrame.linkPenColor=QColorConstants.DarkRed
        # Adjust sizes for different style margins etc
        for node in self.graphFrame.findChildren(GraphNode):
            node.adjustSize()
    
    def toggle_links(self):
        """
        Toggles whether link are shown to the variables list node
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

    def import_bpd(self):
        """
        Shows the BPD import window to load a new BPD from input text
        """
        from bpdeditor.bpd_import_window import BPDImportWindow
        self.bpd_import_window = BPDImportWindow(self.settings, self.app, self)
        self.toolbar.action_bpd_import.setChecked(True)
        
    def export_bpd(self):
        """
        Produces the obj dump text for the current BPD
        """
        self.toolbar.action_bpd_export.setChecked(True)
        exportNode = copy.deepcopy(self.node)
        exportNode.has_data = True
        exportNode.data = ['Here is your exported dump:']
        for idx,seq in enumerate(self.sequences):
            seq.Reconsolidate(self.graphFrame.sequenceGraphs[idx])
            exportNode.data.append(f' BehaviorSequences({idx})=(BehaviorSequenceName=\"{seq.Name}\",{seq.PrintDump()}),')
        exportNode.data[-1]=exportNode.data[-1].removesuffix(',')
        self.bpd_window = BPDExportWindow(self.settings, self.app, exportNode)

