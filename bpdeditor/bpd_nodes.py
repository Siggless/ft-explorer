from typing import List
from PyQt5.QtWidgets import *
from PyQt5.QtGui import *
from PyQt5.QtCore import *

from .bpd_classes import *
from .bpd_gui import *

from .model_sequenceItem import *
from .model_event import *
from .model_behavior import *
from .view_outLinks import *
from .view_varLinks import *
from .view_variable import *

# Load our generated json dictionaries for auto-completers and var link suggestions
import json, inspect
from os import path
#behaviorFilePath = path.join("bpdeditor/behaviors.json")
behaviorFilePath = path.join(path.dirname(path.abspath(inspect.getfile(inspect.currentframe()))) , "behaviors.json")
behaviorDict = json.load(open(behaviorFilePath))
behaviorDict={k:v for k,v in sorted(behaviorDict.items())}    # Sort alphabetically
#eventFilePath = path.join("bpdeditor/behaviors.json")
eventFilePath = path.join(path.dirname(path.abspath(inspect.getfile(inspect.currentframe()))), "events.json")
eventDictFull:dict = json.load(open(eventFilePath))
eventDictFull={k:v for k,v in sorted(eventDictFull.items())}   # Sort alphabetically
# There are a lot of junk events so filter this one for the Completers
eventWhitelist = ["On","Damaged","Killed"]
eventDict={k:v for k,v in eventDictFull.items() if any(k.startswith(prefix) for prefix in eventWhitelist)}


class SequenceGraph(Graph):
    """A single BPD sequence's node tree"""
    def __init__(self, canvas:GraphCanvas, sequence:BehaviorSequence):
        super().__init__(canvas)
        self.sequence: BehaviorSequence = sequence
        self.sequenceNodes: List[SequenceNode] = []
        self.varNode: VarsNode = None
    
    def Paint(self, qp: QPainter, pen: QPen, drawVarConnections: bool, linkPenColor: QColor):
        for child in self.sequenceNodes:
            # Output-to-Input Variables
            linkPenColor.setAlpha(210)
            child.Paint(qp, pen, QPen(linkPenColor, 2))
            
            # Variable Links
            if hasattr(child, 'varLinkList'):
                if drawVarConnections or child.isSelected:
                    # Unselected nodes have alpha to make it less painful
                    if not child.isSelected:
                        linkPenColor.setAlpha(100)
                    else:
                        linkPenColor.setAlpha(255)
                    qp.setPen(QPen(linkPenColor))
                    
                    varNode = self.varNode
                    for link in child.varLinkList.items:
                        for varDropdown in link.varDropdownList:
                            # Get the dropdown index - that should match the row id in the vars node
                            id = varDropdown.currentIndex()
                            if id >= 0 and len(varNode.items) > id:
                                varRowButton = varNode.items[id].removeButton
                                c = self.canvas
                                
                                posTo = midPoint(varRowButton.mapTo(c,varRowButton.rect().topRight()), varRowButton.mapTo(c,varRowButton.rect().bottomRight()))
                                if varNode.mapTo(c,varNode.rect().center()).x() < child.mapTo(c,child.rect().center()).x():
                                    posTo.setX(varNode.mapTo(c,varNode.rect().topRight()).x())
                                else:
                                    posTo.setX(varNode.mapTo(c,varNode.rect().topLeft()).x())
                                
                                if not child.varLinkList.isVisible():
                                    # If vars not expanded then draw from button
                                    button = child.varLinkButton
                                    posFrom = midPoint(button.mapTo(c,button.rect().topLeft()),button.mapTo(c,button.rect().bottomLeft()))
                                else:
                                    # If vars list is expanded then draw from items
                                    posFrom = midPoint(varDropdown.mapTo(c,varDropdown.rect().topLeft()), varDropdown.mapTo(c,varDropdown.rect().bottomLeft()))
                                    
                                if varNode.mapTo(c,varNode.rect().center()).x() < child.mapTo(c,child.rect().center()).x():
                                    posFrom.setX(child.mapTo(c,child.rect().topLeft()).x())
                                else:
                                    posFrom.setX(child.mapTo(c,child.rect().topRight()).x())
                                qp.drawLine(posFrom, posTo)

    def MakeNodes(self):
        """
        Create the GraphNodes for this BehaviorSequence data
        """
        self.rootNode = GraphNode(f"SEQUENCE ROOT {self.sequence.Name}", self, self.canvas)
        self.rootNode.setFixedSize(0,0)
        #self.sequenceNodes.append(self.rootNode)   # Show event connections to the sequence root
        
        # First make a fake connection to this sequence's Variables node so it's on the left of the rest
        self.varNode = VarsNode(self, self.canvas)
        self.rootNode.outConnections.append(Connection(self.rootNode, -1, self.varNode, -1))
        
        eventModel = self.sequence.eventModel
        for i in range(eventModel.rowCount()):
            node = EventNode(eventModel.item(i), self, self.canvas)
            self.rootNode.outConnections.append(Connection(self.rootNode, -1, node, -1))
        behModel = self.sequence.behaviorModel
        for i in range(behModel.rowCount()):
            node = BehaviorNode(behModel.item(i), self, self.canvas)
    
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
        for child in self.sequenceNodes:
            if not child.model:
                continue
            
            child.MakeOutConnections()
            child.MakeVarConnections()
            
    def FindNode(self, item: BehaviorItem):
        """ Returns the node for the given BehaviorData object"""
        for child in self.sequenceNodes:
            if child.modelItem is item:
                return child
            
    def FindNode(self, index: int):
        """ Returns the node with the given BehaviorModel's index"""
        for child in self.sequenceNodes:
            if type(child) is BehaviorNode:
                if child.mapper.model() and child.mapper.currentIndex() == index:
                    return child
    
    def NewEventNode(self):
        newItem = self.sequence.eventModel.newItem()
        node = EventNode(newItem, self, self.canvas)
        node.move(self.canvas.rect().center())
        node.show()
        self.rootNode.outConnections.append(Connection(self.rootNode,-1,node,-1))
        self.canvas.parent().toolbar.action_new_event.setChecked(True)
        
    def NewBehaviorNode(self):
        newItem = self.sequence.behaviorModel.newItem()
        node = BehaviorNode(newItem, self, self.canvas)
        node.move(self.canvas.rect().center())
        node.show()
        self.rootNode.outConnections.append(Connection(self.rootNode,-1,node,-1))
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
            
            while type(source) is not NodeCombo and not issubclass(type(source), GraphNode):
                source = source.parentWidget()
                if source is None or source is self:
                    return
            while type(dest) is not NodeCombo and not issubclass(type(dest), GraphNode):
                dest = dest.parentWidget()
                if dest is None or dest is self:
                    return
                
            # Check we're linking within the same BehaviorSequence
            sourceNode = source
            while not issubclass(type(sourceNode),GraphNode) and sourceNode is not self: sourceNode = sourceNode.parentWidget()
            destNode = dest
            while not issubclass(type(destNode),GraphNode) and destNode is not self: destNode = destNode.parentWidget()
            if not (sourceNode.graph is self and destNode.graph is self):
                QMessageBox.information(self.canvas, 'Whoops', "Can't link across separate BehaviorSequences!")
                return
            
            if type(dest) is BehaviorNode and issubclass(type(source), SequenceNode):
                # New output link
                index = dest.modelItem
                source.outLinkList.NewRow(index.row())
            elif type(dest) is VarsNode and issubclass(type(source), SequenceNode):
                # New variable link to a new variable
                dest.NewVariable()
                index = len(dest.items) - 1
                source.varLinkList.NewRow(index)
                
            elif issubclass(type(dest), GraphNode) and type(source) is NodeCombo:
                # From combo to node
                if source.enterHover is HoveringOver.OUT_LINK_COMBO and type(dest) is BehaviorNode:
                    index = dest.modelItem.row()
                    source.setCurrentIndex(index)
                elif source.enterHover is HoveringOver.VAR_LINK_COMBO and type(dest) is VarsNode:
                    dest.NewVariable()
                    index = len(dest.items)-1
                    source.setCurrentIndex(index)
                    
            elif type(dest) is NodeCombo and issubclass(type(source),SequenceNode):
                # From node to combo
                if dest.enterHover is HoveringOver.VAR_NODE_COMBO:
                    for i, item in enumerate(self.varNode.items):
                        if item.dropdown is dest:
                            index = i
                            break
                    source.varLinkList.NewRow(index)
                elif dest.enterHover is HoveringOver.VAR_LINK_COMBO:
                    source.varLinkList.NewRow(dest.currentIndex())
                    
            elif type(dest) is NodeCombo and type(source) is NodeCombo:
                # From combo to combo
                if source is dest:
                    return
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
BPD Specific Node Classes
"""
class SequenceNode(GraphNode):
    """ Base node for Events and Behaviors - having Output Links and Variable Links """
    def __init__(self, title, graph: SequenceGraph, parent, modelItem):
        super().__init__(title, graph, parent)
        if graph:
            graph.sequenceNodes.append(self)
        self.modelItem: SequenceItem = modelItem
        self.model = self.modelItem.model()
        #self.model: SequenceItemModel = model
        #self.modelItem: SequenceItem = self.model.item(modelIndex)
        # A persistent model index updates with the model events
        #self.modelIndex: QPersistentModelIndex = QPersistentModelIndex(model.index(modelIndex, 0))
        
        varLinkIDs = self.modelItem.GetAllVarLinkIndexes()
        self.varLinkList: VarLinksList = VarLinksList(self, varLinkIDs)
        outLinkIDs = self.modelItem.GetAllOutLinkIndexes()
        self.outLinkList: OutputLinksList = OutputLinksList(self, outLinkIDs)
        self.varLinkButton = NodeButton("Variables")
        self.varLinkButton.SetHover(HoveringOver.VAR_LINK_BUTTON, HoveringOver.GRAPH_NODE)
        self.varLinkButton.clicked.connect(self.VarLinkToggle)
        self.outLinkButton = NodeButton("Output Links")
        self.outLinkButton.SetHover(HoveringOver.OUT_LINK_BUTTON, HoveringOver.GRAPH_NODE)
        self.outLinkButton.clicked.connect(self.OutLinkToggle)

        layout = QVBoxLayout(self)
        self.nodeLayout = QGridLayout()
        """ The inner QLayout for this node's custom widgets """
        layout.addLayout(self.nodeLayout)
        layout.addWidget(self.varLinkButton)
        layout.addWidget(self.varLinkList)
        layout.addWidget(self.outLinkButton)
        layout.addWidget(self.outLinkList)
    
    def MakeOutConnections(self):
        # Reverse as we're editing a list that we're iterating over...
        for con in reversed(self.outConnections):
            con.Remove()
        
        outLinkItems = self.modelItem.GetAllOutLinkItems()
        for i, modelItem in enumerate(outLinkItems):
            conny = OutputLinkConnection(self.graph, modelItem, self, i)
            self.outConnections.append(conny)
    
    def MakeVarConnections(self):
        # Reverse as we're editing a list that we're iterating over...
        for con in reversed(self.inConnections):
            if con.destIndex >= 0:  # I.E. if a var connection
                con.Remove()
        for con in reversed(self.varConnections):
            if con.destIndex >= 0:  # I.E. if a var connection
                con.Remove()
        
        for i, link in enumerate(self.modelItem.GetAllVarLinkItems()):
            for varIdx in link.GetAllVariableIndexes():
                if varIdx >= 0:
                    if self.graph.varNode:
                        self.varListConnections.append(Connection(self,i,self.graph.varNode,varIdx))
                    
                    # Check for shared variables with other nodes
                    # TODO make this just pass a signal through the variable model item
                    #  since nodes we are concerned about are already linked to that
                    if link.VariableLinkType == VariableLinkTypes.BVARLINK_Output:
                        # Is this variable used in another node?
                        for node in self.graph.sequenceNodes:
                            for idx2, link2 in enumerate(node.modelItem.GetAllVarLinkItems()):
                                if link2.VariableLinkType != VariableLinkTypes.BVARLINK_Output:
                                    for varIdx2 in link2.GetAllVariableIndexes():
                                        if varIdx is varIdx2:
                                            self.varConnections.append(Connection(self,i,node,idx2))
                                            break
                    else:
                        # Is this variable set in another node?
                        for node in self.graph.sequenceNodes:
                            for idx2, link2 in enumerate(node.modelItem.GetAllVarLinkItems()):
                                if link2.VariableLinkType == VariableLinkTypes.BVARLINK_Output:
                                    for varIdx2 in link2.GetAllVariableIndexes():
                                        if varIdx is varIdx2:
                                            node.varConnections.append(Connection(node,idx2,self,i))
                                            break
    
    def VarLinkToggle(self):
        if self.varLinkList.isVisible():
            self.varLinkList.hide()
        else:
            self.varLinkList.show()
        self.graph.canvas.update()
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
        self.graph.canvas.update()
        # Reposition to keep centered
        oldCentre = self.rect().center()
        self.adjustSize()
        newCentre = self.rect().center()
        self.move(self.pos().x() + (oldCentre - newCentre).x(), self.pos().y())

    def Select(self):
        super().Select()
        self.canvas.parent().toolbar.action_delete.setCheckable(True)
        self.canvas.parent().toolbar.action_delete.setChecked(True)

    def Delete(self):
        """
        Delete this node, its connections, and its data from the sequence.
        """
        self.model.removeRow(self.modelItem.row())
        self.graph.sequenceNodes.remove(self)
        
        for con in reversed(self.inConnections):
            if type(con) is not OutputLinkConnection:
                con.Remove()
            else:
                con.ChangeDestination(None, -1)
        for con in reversed(self.outConnections): con.Remove()
        for con in reversed(self.varConnections): con.Remove()
        for con in reversed(self.varListConnections): con.Remove()

        self.deleteLater()

class EventNode(SequenceNode):
    def __init__(self, modelItem: EventItem, graph: SequenceGraph, parent):
        super().__init__("Event", graph, parent, modelItem)
        
        self.userDataList = DictionaryList(self, modelItem)
        self.eventNameBox: QLineEdit = self.userDataList.items[0][1]
        completer = QCompleter(eventDict.keys(), self)
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
                while len(self.varLinkList.items) > 0: self.varLinkList.RemoveRow()
                # Add in the new var links from the dictionary
                for k, v in sorted(eventLinks.items()):
                    self.varLinkList.NewRow()
                    newIndex = self.varLinkList.items[-1].mapper.currentIndex()
                    newItem: VarLinkItem = self.varLinkList.sequence.varLinkModel.item(newIndex)
                    newItem.ConnectionIndex = int(k)
                    newItem.PropertyName = v['PropertyName'][0]
                    newItem.VariableLinkType = VariableLinkTypes[v['VariableLinkType'][0]]

        self.messageBoxShown = False
        self.sender().clearFocus()


class BehaviorNode(SequenceNode):
    def __init__(self, modelItem: BehaviorItem, graph: SequenceGraph, parent):
        super().__init__("Behavior", graph, parent, modelItem)
       
        l0 = QLabel("Class")
        self.p0 = QLineEdit()
        completer = QCompleter(behaviorDict.keys(), self)
        completer.setCaseSensitivity(Qt.CaseInsensitive)
        self.p0.setCompleter(completer)
        self.p0.editingFinished.connect(self.BehaviorClassChanged)
        self.messageBoxShown = False
        l1 = QLabel("Object")
        self.p1 = QLineEdit()
        
        layout = self.nodeLayout
        layout.addWidget(l0,0,0)
        layout.addWidget(self.p0,0,1)
        layout.addWidget(l1,1,0)
        layout.addWidget(self.p1,2,0,1,2)
        
        self.mapper = QDataWidgetMapper(self)
        self.mapper.setModel(self.model)
        self.mapper.addMapping(self.p0, 0)
        self.mapper.addMapping(self.p1, 1)
        self.mapper.setCurrentIndex(modelItem.row())
        
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
                    newIndex = self.varLinkList.items[-1].mapper.currentIndex()
                    newItem: VarLinkItem = self.varLinkList.sequence.varLinkModel.item(newIndex)
                    newItem.ConnectionIndex = int(v['ConnectionIndex'][0])
                    newItem.PropertyName = k
                    newItem.VariableLinkType = VariableLinkTypes[v['VariableLinkType'][0]]

        self.messageBoxShown = False
        self.sender().clearFocus()


class DictionaryList(QFrame):
    """ The widget list for extra node data. """
    def __init__(self, parent: SequenceNode, modelItem: EventItem):
        super().__init__(parent)
        self.parentNode: SequenceNode = parent
        self.modelItem = modelItem
        model = modelItem.model()
        
        layout = self.parentNode.nodeLayout
        self.items = []
        self.mapper = QDataWidgetMapper(parent)
        self.mapper.setModel(model)
        # Add a label and textbox/checkbox for each dictionary key/value pair
        modelItems = [model.data(model.index(modelItem.row(), c), Qt.UserRole) for c in range(model.columnCount())]
        for i, (key, value) in enumerate(modelItems):
            if key == 'FilterObject':
                continue    # Don't care about this one
            
            label = QLabel(key)
            layout.addWidget(label, i, 0)
            if type(value) is bool:
                # Bools are a checkbox
                item = QCheckBox()
            else:
                # Anything else is a textbox
                item = QLineEdit()
            
            label.setBuddy(item)
            layout.addWidget(item, i, 1)
            self.items.append((label, item))
            self.mapper.addMapping(item, i)
            
        self.mapper.setCurrentIndex(modelItem.row())
