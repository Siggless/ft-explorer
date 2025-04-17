from __future__ import annotations
import qdarkgraystyle
from typing import List
from PyQt5.QtWidgets import *
from PyQt5.QtGui import *
from PyQt5.QtCore import *

from bpdeditor.bpd_classes import *
from bpdeditor.bpd_export_window import BPDExportWindow

"""
This file contains everything for the main BPD Editor window.
Would be nice to use a proper QGraphicsScene to be able to zoom in
 and out, but that's beyond me. Nick something like NodeGraphQT or 
 qtpynodeeditor.
"""

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
    hover: HoveringOver = HoveringOver.BACKGROUND
    drawVarConnections: bool = True
    linkPenColor: QColor = QColorConstants.DarkRed
    
    def __init__(self):
        super().__init__()
        self.setFrameStyle(QFrame.StyledPanel | QFrame.Sunken)
        self.setLineWidth(5)
        self.setStyleSheet(self.styleSheet() + '\n*[selected="true"] { border: 2px solid orange; }')
        self.tooltipLabel:QLabel = QLabel(self)
        self.tooltipLabel.move(0,0)

        self.graphs: List[Graph] = []
        self.rootNode = GraphNode("CANVAS ROOT", None, self)
        self.rootNode.setFixedSize(0, 0)

        self.isSelecting:bool = False
        self.selectStartPos:QPoint = QPoint()
        self.selectEndPos:QPoint = QPoint()
        self.selectedNodes:List[GraphNode]=[]
        self.lastSelectedGraph:Graph = None
        
        # Vars for drag operation - yeah bodgey
        self.isDragging:bool = False
        self.dragObject = None
        self.dragObjectPos:QPoint = QPoint()
        self.dragStartPos:QPoint = QPoint()
        self.dragEndPos:QPoint = QPoint()
        
        self.isPanning:bool = False
        self.panStartPos:QPoint = QPoint()
        self.panEndPos:QPoint = QPoint()
        
        self.isLinking:bool =False
        self.linkSource=None
        self.linkDest=None
        
    def AddGraph(self, graph: Graph):
        """Adds the given graph and connects it to the canvas rootNode"""
        self.graphs.append(graph)
        self.rootNode.outConnections.append(Connection(self.rootNode, -1, graph.rootNode, -1))
               
    def OrganiseTree(self):
        """
        Works well enough - checks for intersections on a node's level in the tree.
        Assuming all nodes are the same height (so levels don't overlap)
        """

        for node in self.findChildren(GraphNode):
            node.hasBeenPositioned=False

        def PositionBranch(node: GraphNode, branchCentrePos: QPoint, level) -> QRect:
            """
            Positions the node based on its parent's current position, avoiding other nodes on its level
             Returns the bounding box for this node, after positioning
            """

            if node.hasBeenPositioned:
                # We've already hit this one so ignore
                return node.geometry()
            if len(levelBBoxes) <= level:
                levelBBoxes.append(QRect())
            levelBox = levelBBoxes[level]
            
            halfWidth:QPoint = QPoint(int(node.width() / 2) - 1, 0)
            node.move(branchCentrePos - halfWidth)

            # Shift the position if intersecting with this row's bbox
            intersectBox = levelBox.intersected(node.geometry())
            if intersectBox.width() > 0:
                branchDelta = QPoint(levelBox.topRight().x() - node.geometry().x() + xPadding, 0)
                branchCentrePos = branchCentrePos + branchDelta
            node.move(branchCentrePos - halfWidth)

            node.hasBeenPositioned = True # Here in case children loop back to this node
            
            numChildren = len(node.outConnections)
            if numChildren > 0:
                xSpacing:int = node.outConnections[0].destNode.width() + xPadding
                ySpacing:int = node.height() + yPadding
                allChildBox:QRect = QRect()
                newPos:QPoint = branchCentrePos + QPoint(0, ySpacing)
                #newPos = branchCentrePos + QPoint(-int(xSpacing*(numChildren-1)/2), ySpacing)
                for i in range(numChildren):
                    child:GraphNode = node.outConnections[i].destNode
                    if not child.hasBeenPositioned:
                        childBox = PositionBranch(child, newPos, level + 1)
                        allChildBox = allChildBox.united(childBox)
                        newPos = allChildBox.topRight() + QPoint(xPadding, 0)
                if allChildBox.isValid():
                    branchCentrePos.setX(allChildBox.center().x())
                node.move(branchCentrePos - halfWidth)
            
            # And check for intersections AGAIN to fix cases where a child has multiple parents
            intersectBox = levelBox.intersected(node.geometry())
            if intersectBox.width() > 0:
                node.move(QPoint(levelBox.topRight().x() + xPadding, branchCentrePos.y()))
                
            levelBox = levelBox.united(node.geometry())
            levelBBoxes[level] = levelBox
            return node.geometry()
        
        levelBBoxes: List[QRect] = []
        xPadding = 50
        yPadding = 50
            
        # OK let's do this
        PositionBranch(self.rootNode, QPoint(0, -yPadding*2), 0)
                    
    def ClearCanvas(self):
        """ Removes all graphs and nodes, except the root node """
        for child in self.findChildren(GraphNode):
            if child is self.rootNode:
                child.outConnections = []
                continue
            child.deleteLater()
            self.graphs = []
            self.lastSelectedGraph = None
            self.selectedNodes = []
    
    def ExpandAll(self):
        """
        Expands all variable and outputlink lists on all nodes, then reorganises the tree
        """
        from .bpd_nodes import SequenceNode
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
        from .bpd_nodes import SequenceNode
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
        for node in reversed(self.selectedNodes):
            node.Deselect()
        self.selectedNodes=[]
        self.isSelecting=False
        self.parent().toolbar.action_delete.setCheckable(False)
        self.parent().toolbar.action_delete.setChecked(False)
    
    def DeleteSelectedNodes(self):
        for node in reversed(self.selectedNodes):
            node.Deselect()
            node.Delete()
        self.parent().toolbar.action_delete.setCheckable(False)
        self.parent().toolbar.action_delete.setChecked(False)
    
    def NewEventNode(self):
        if self.lastSelectedGraph:
            self.lastSelectedGraph.NewEventNode()
        else:
            QMessageBox.information(self, "New Node", "The node is added to the last selected sequence. \
                               <br>First select a node in the relevant sequence graph!")
        self.parent().toolbar.action_new_event.setChecked(True)
    
    def NewBehaviorNode(self):
        if self.lastSelectedGraph:
            self.lastSelectedGraph.NewBehaviorNode()
        else:
            QMessageBox.information(self, "New Node", "The node is added to the last selected sequence. \
                               <br>First select a node in the relevant sequence graph!")
        self.parent().toolbar.action_new_behavior.setChecked(True)
    
    
    def paintEvent(self, event):
        """ Handles painting connections, input rectangles and tooltips """
        super().paintEvent(event)
        
        # Draw all connections
        qp = QPainter(self)
        qp.setRenderHint(QPainter.Antialiasing)
        defaultPen = qp.pen()   # From style to keep light/dark mode
        defaultPen.setWidth(2)

        for graph in self.graphs:
            graph.Paint(qp, defaultPen, self.drawVarConnections, self.linkPenColor)
        
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
        self.tooltipLabel.move(10, 10)
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
                        if selectangle.intersects(node.geometry()):
                            node.Select()
                            
        
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


class Graph():
    """A single base node graph"""
    def __init__(self, canvas: GraphCanvas):
        self.canvas: GraphCanvas = canvas
        self.rootNode: GraphNode = canvas.rootNode
        self.nodes: List[GraphNode] = []
    
    def Paint(self, *args):
        pass
    
    def MakeNodes(self):
        """
        Create the GraphNodes for this BehaviorSequence data
        """
        pass
    
    def MakeConnections(self):
        """
        Create the connections between this sequence's GraphNodes
        Called once all nodes have been created
        """
        Connections = []
        pass

"""
Abstract Node Classes
Mostly to handle user inputs on all nodes
"""
class GraphNode(QGroupBox):
    """ Base Node class """
    def __init__(self, title, graph, parent):
        super().__init__(title, parent)
        self.graph: Graph = graph
        self.canvas: GraphCanvas = parent
        self.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Maximum)

        self.inConnections: List[Connection] = []
        """ Connections from other nodes - automatically added when a Connection in initialised """  
        self.outConnections: List[Connection] = []
        """ Connections from this node's output links """
        self.varConnections: List[Connection] = []
        """ Connections to other node that gives an output to a variable we input """
        self.varListConnections: List[Connection] = []
        """ Connections to the variable list node """
        
        self.hasBeenPositioned: bool = False
        self.isSelected: bool = False
        
    def Select(self):
        if self not in self.canvas.selectedNodes:
            self.isSelected=True
            self.canvas.selectedNodes.append(self)
            self.canvas.lastSelectedGraph = self.graph
            self.setProperty("selected","true")
            self.setStyleSheet(self.canvas.styleSheet())
    
    def Deselect(self):
        self.canvas.selectedNodes.remove(self)
        self.isSelected=False
        self.setProperty("selected", "false")
        self.setStyleSheet(self.canvas.styleSheet())
    
    def Delete(self):
        pass
    
    def Paint(self, qp: QPainter, pen: QPen, linkPen: QPen):
        qp.setPen(linkPen)
        for con in self.varConnections:
            con.Paint(qp, True)
        qp.setPen(pen)
        for con in self.outConnections:
            con.Paint(qp, False)

    
    def mousePressEvent(self, event):
        self.raise_()
        self.adjustSize()
        if event.button() == _PRIMARY_BUTTON and not self.canvas.isLinking:
            self.canvas.dragObject = self
            self.canvas.dragObjectPos = event.pos()
            self.canvas.dragStartPos = event.pos()+self.pos()
            if self not in self.canvas.selectedNodes:
                self.canvas.ClearSelection()
                self.Select()
        
    def mouseReleaseEvent(self, event):
        self.adjustSize()
        if event.button() == _SECONDARY_BUTTON and self.canvas.isLinking:
            self.canvas.isLinking = False
            self.canvas.linkDest = self
            self.graph.QuickLink(self.canvas.linkSource, event)
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
            self.GetGraphNode().graph.QuickLink(canvas.linkSource, event)
    
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
    """
    Just a QComboBox, but has multiple inheritance to send link events and update our tooltips,
    and update the model on currentIndexChanged, instead of just textChanged.
    """
    def __init__(self, parent=None):
        super().__init__()
        # I want to update the model on currentIndexChanged too, when scrolling.
        # I can't find which signal actually updates it, only the clearFocus().
        # Yes this is the best bodge I can think of.
        #self.currentIndexChanged.connect(lambda int: (self.clearFocus(), self.setFocus()))
        self.currentIndexChanged.connect(lambda int: (self.setFocus(), self.clearFocus(), self.setFocus()))
        #self.currentIndexChanged.connect(lambda int: self.editTextChanged.emit(self.currentText()))
    
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

    def ChangeDestination(self, destNode:GraphNode, destIndex):
        self.destNode.inConnections.remove(self)
        
        self.destNode = destNode
        if self.destNode and self not in self.destNode.inConnections:
            self.destNode.inConnections.append(self)
        self.destIndex = destIndex

    def Remove(self) -> None:
        if self.destNode:
            if self in self.destNode.inConnections:
                self.destNode.inConnections.remove(self)
        if self.sourceNode:
            if self in self.sourceNode.outConnections:
                self.sourceNode.outConnections.remove(self)
            if self in self.sourceNode.varConnections:
                self.sourceNode.varConnections.remove(self)
            if self in self.sourceNode.varListConnections:
                self.sourceNode.varListConnections.remove(self)
        del self

    def Paint(self, qp:QPainter, offset:bool):
        """Draws the connection as a swanky cubic bezier"""
        if not self.destNode:
            return
        
        endOffset:QPoint = QPoint(10*(self.destIndex+2), 10) if offset else QPoint(0,10)
        end:QPoint = midPoint(self.destNode.geometry().topLeft(), self.destNode.geometry().topRight()) + endOffset
        
        if self.sourceNode is not self.destNode:
            startOffset:QPoint = QPoint(10*(self.sourceIndex+2), 0) if offset else QPoint()
            start:QPoint = midPoint(self.sourceNode.geometry().bottomLeft(), self.sourceNode.geometry().bottomRight()) + startOffset
            bezierPath:QPainterPath = QPainterPath(start)
            bezierPath.cubicTo(start + QPoint(0, 40 if offset else 30), end - QPoint(0, 30), end)
            qp.drawPath(bezierPath)
        else:
            startOffset:QPoint = QPoint(10*(self.sourceIndex+2), 10) if offset else QPoint(0,10)
            start:QPoint = midPoint(self.sourceNode.geometry().topLeft(), self.sourceNode.geometry().topRight()) + startOffset
            bezierPath:QPainterPath = QPainterPath(start)
            bezierPath.cubicTo(start - QPoint(0, 10), end - QPoint(0, 10), end)
            qp.drawPath(bezierPath)

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
        self.action_expand = self.addAction('Expand All', parent.canvas.ExpandAll)
        self.action_expand.setCheckable(True)
        self.action_expand.setChecked(True)
        self.action_collapse = self.addAction('Collapse All', parent.canvas.CollapseAll)
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
        
        self.action_new_behavior = self.addAction('New Behavior', parent.canvas.NewBehaviorNode)
        self.action_new_behavior.setToolTip('Adds a Behavior to the last selected BehaviorSequence')
        self.action_new_behavior.setCheckable(True)
        self.action_new_behavior.setChecked(True)
        self.action_new_event = self.addAction('New Event', parent.canvas.NewEventNode)
        self.action_new_event.setToolTip('Adds an Event to the last selected BehaviorSequence')
        self.action_new_event.setCheckable(True)
        self.action_new_event.setChecked(True)
        self.action_delete = self.addAction('Delete Behavior/Event', parent.canvas.DeleteSelectedNodes)
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
        self.canvas = GraphCanvas()
        self.setCentralWidget(self.canvas)
        self.canvas.drawVarConnections = self.settings.value('bpdwindow/showLinks', False, type=bool)
        
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
            self.canvas.linkPenColor=QColorConstants.Red
            self.canvas.linkPenColor=QColorConstants.Svg.orangered
            #self.canvas.linkPenColor=QColorConstants.Svg.darkorange
        else:
            self.app.setStyleSheet('')
            self.canvas.linkPenColor=QColorConstants.DarkRed
        # Adjust sizes for different style margins etc
        for node in self.canvas.findChildren(GraphNode):
            node.adjustSize()
    
    def toggle_links(self):
        """
        Toggles whether link are shown to the variables list node
        """
        self.settings.setValue('bpdwindow/showLinks', self.sender().isChecked())
        self.canvas.drawVarConnections = self.sender().isChecked()
        self.canvas.update()
        
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
        from .bpd_nodes import SequenceGraph
        for seq in self.sequences:
            sequenceGraph = SequenceGraph(self.canvas, seq)
            sequenceGraph.MakeNodes()
            self.canvas.AddGraph(sequenceGraph)

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
        self.setFocus()     # End widgets currently in edit mode, to update the model
        self.toolbar.action_bpd_export.setChecked(True)
        exportNode = copy.deepcopy(self.node)
        exportNode.has_data = True
        exportNode.data = []
        for idx, seq in enumerate(self.sequences):
            seq.Reconsolidate()
            exportNode.data.append(f'BehaviorSequences({idx})=(BehaviorSequenceName=\"{seq.Name}\",{seq.PrintDump()}),')
        exportNode.data[-1] = exportNode.data[-1].removesuffix(',')
        self.bpd_window = BPDExportWindow(self.settings, self.app, exportNode)
