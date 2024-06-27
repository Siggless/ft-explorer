#!/usr/bin/env python3
# vim: set expandtab tabstop=4 shiftwidth=4:

# Copyright (c) 2018, CJ Kucera
# All rights reserved.
#   
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#     * Redistributions of source code must retain the above copyright
#       notice, this list of conditions and the following disclaimer.
#     * Redistributions in binary form must reproduce the above copyright
#       notice, this list of conditions and the following disclaimer in the
#       documentation and/or other materials provided with the distribution.
#     * Neither the name of the development team nor the
#       names of its contributors may be used to endorse or promote products
#       derived from this software without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND
# ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
# DISCLAIMED. IN NO EVENT SHALL CJ KUCERA BE LIABLE FOR ANY
# DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES
# (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
# LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND
# ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
# (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
# SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

import os
import sys
import struct
import argparse
from ftexplorer.data import Data
from level_sequence_event_names import level_sequence_event_names

###
### WARNING: Here there be dragons.
###
### This code's gotten quite unweildy, sorry about that.  A lot of stuff is
### implemented separately in like two or three different places throughout
### the file.  Rather than refactor everything to use a common codebase, when
### I implemented the Kismet stuff, I just sort of tacked it on to the
### existing BPD-processing stuff, as its own separate thing.  It's... rather
### hokey.  Still, things seem to work pretty well, at least.  Anyway, beware.
### The code used to be pretty reasonable -- not so much, anymore.
###

###
### Color/shape information
###

style_default = 'shape=box style=rounded'
style_bpd_edge = 'fontsize=11'
style_kismet_default = 'shape=box style="rounded,filled" fillcolor=cadetblue1'
style_broken_cold = 'style=filled fillcolor=red'
style_event = 'style=filled fillcolor=chartreuse2'
style_event_edge = 'color=chartreuse2'
style_event_invalid = 'style=filled fillcolor=lightpink2 shape=cds margin=0.15'
style_event_remote = 'style=filled fillcolor=gold1 shape=cds margin=0.15'
style_seq_event = 'style=filled fillcolor=deepskyblue1'
style_event_unknown = 'style=filled fillcolor=deepskyblue1'
style_seq_event_edge = 'color=deepskyblue1'
style_seq_var = 'shape=ellipse style=filled fillcolor=lemonchiffon1'
style_seq_var_edge = 'color=lemonchiffon4 style=dashed'

###
### Class for dealing with kismet-style sequence objects.
###

class KismetBaseNode(object):
    """
    Base attributes all nodes should have
    """

    def __init__(self, node_id):
        self.node_id = node_id

        # This is populated by the main Kismets class when linking nodes together,
        # and is only actually used if we need to re-calculate our change points
        # after loading a full sequence (rather than specifying a start point)
        self.links_in = set()
        self.links_out = set()

class KismetBaseRealNode(KismetBaseNode):
    """
    Some base node functionality we want in "real" nodes (seqact, seqvar, etc...)
    """

    def __init__(self, name, node_id, prev_node=None):
        super().__init__(node_id)
        self.name = name
        (self.base_class, self.short_name) = name.rsplit('.', 1)
        if prev_node:
            if self.base_class.lower() == prev_node.base_class.lower():
                self.change_point = False
            else:
                self.change_point = True
        else:
            self.change_point = True

    def update_change_point(self, prev_node):
        """
        Given a `prev_node`, mark ourselves as a "change point" if the classes
        don't actually match
        """
        if prev_node and self.base_class.lower() != prev_node.base_class.lower():
            self.change_point = True

class KismetUnknownEventNode(KismetBaseNode):
    """
    Custom object to describe an event we don't know how to get to
    """

    def __init__(self, node_id, event_name):
        super().__init__(node_id)
        self.event_name = event_name

    def get_style(self):
        global style_event_unknown
        return '{} '.format(style_event_unknown)

    def get_label(self):
        return '{}<br/><i>(Unknown Event,<br/>may call out to other BPD)</i>'.format(self.event_name)

    def update_change_point(self, prev_node):
        pass

class KismetUnknownExactBPD(KismetBaseNode):
    """
    Custom object to describe a BPD Event we don't have loaded
    """

    def __init__(self, node_id, bpd_name, event_name):
        super().__init__(node_id)
        self.bpd_name = bpd_name
        self.event_name = event_name

    def get_style(self):
        global style_event_remote
        return '{} '.format(style_event_remote)

    def get_label(self):
        if ':' in self.bpd_name:
            (first, second) = self.bpd_name.split(':', 1)
            return '{}:<br/>{}<br/>{}'.format(first, second, self.event_name)
        else:
            return '{}<br/>{}'.format(self.bpd_name, self.event_name)

    def update_change_point(self, prev_node):
        pass

class KismetNode(KismetBaseRealNode):
    """
    A single Kismet sequence object
    """

    def __init__(self, name, node_id, data, prev_node, from_bpd, bpd_event_map):
        global get_rce_bpd
        super().__init__(name, node_id, prev_node)
        self.struct = data.get_struct_by_full_object(name)
        self.event_name = None
        self.event_link = None
        if 'EventName' in self.struct:
            if (self.short_name.lower().startswith('seqevent_remoteevent') or
                    self.short_name.lower().startswith('willowseqevent_missionremoteevent')):
                self.event_name = self.struct['EventName']
            else:
                self.event_link = self.struct['EventName']
        self.behaviors = None
        self.behavior_type_report = None
        self.to_behaviors = None
        self.to_events = None
        if 'Behaviors' in self.struct:
            self.behaviors = []
            behavior_types = []
            self.to_behaviors = []
            self.to_events = []
            for behavior_full in self.struct['Behaviors']:
                if behavior_full and behavior_full != '' and behavior_full != 'None':
                    (behavior_type, behavior_name, junk2) = behavior_full.split("'")
                    self.behaviors.append(behavior_name)
                    behavior_types.append(behavior_type)
            if len(behavior_types) == 1:
                self.behavior_type_report = behavior_types[0]
            elif len(behavior_types) > 1:
                self.behavior_type_report = '{} +{} more'.format(
                        behavior_types[0],
                        len(behavior_types)-1,
                        )

            # Read in the behavior data
            for (btype, bname) in zip(behavior_types, self.behaviors):
                bpd_name = None
                event_name = None
                if btype == 'Behavior_RemoteCustomEvent':
                    behavior = data.get_struct_by_full_object(bname)
                    bpd_name = get_rce_bpd(behavior)
                    event_name = behavior['CustomEventName']
                    self.to_behaviors.append((bpd_name, event_name))
                elif btype == 'Behavior_RemoteEvent' or btype == 'Behavior_CustomEvent':
                    if btype == 'Behavior_RemoteEvent':
                        varname = 'EventName'
                    else:
                        varname = 'CustomEventName'
                    behavior = data.get_struct_by_full_object(bname)
                    event_name = behavior[varname]
                    self.to_events.append(event_name)
        
        # Read out output links (this is our primary treeing method)
        self.output_names = []
        if 'OutputLinks' in self.struct and self.struct['OutputLinks'] != '':
            for outputlink in self.struct['OutputLinks']:
                if 'Links' in outputlink and outputlink['Links'] != '':
                    for link in outputlink['Links']:
                        self.output_names.append(Data.get_struct_attr_obj(link, 'LinkedOp'))

        # Read in variables (not doing anything with this yet, but will
        # hopefully be reporting on them)
        self.variable_names = []
        if 'VariableLinks' in self.struct and self.struct['VariableLinks'] != '':
            for variablelink in self.struct['VariableLinks']:
                if 'LinkedVariables' in variablelink and variablelink['LinkedVariables'] != '':
                    linkvars = variablelink['LinkedVariables']
                    # This processing is due to our data library being a bit stupid about
                    # lists of things.  Have to split on the comma ourselves here.
                    for var in linkvars.split(','):
                        (junk, var_name, junk2) = var.split("'")
                        self.variable_names.append(var_name)

        # Read in any events which get triggered.  This seems reasonably rare.
        # TODO: Not sure exactly what happens here; does it just branch off?
        self.event_names = []
        if 'EventLinks' in self.struct and self.struct['EventLinks'] != '':
            for eventlink in self.struct['EventLinks']:
                if 'LinkedEvents' in eventlink and eventlink['LinkedEvents'] != '':
                    linkevents = eventlink['LinkedEvents']
                    # This processing is due to our data library being a bit stupid about
                    # lists of things.  Have to split on the comma ourselves here.
                    for var in linkevents.split(','):
                        (junk, var_name, junk2) = var.split("'")
                        self.event_names.append(var_name)

    def get_label(self):
        label_list = []
        if self.change_point:
            label_list.append('{}.'.format(self.base_class))
        label_list.append(self.short_name)
        if self.event_name:
            label_list.append('Event "{}"'.format(self.event_name))
        if self.behavior_type_report:
            label_list.append('({})'.format(self.behavior_type_report))
        return '<br/>'.join(label_list)

    def get_style(self):
        global style_seq_event
        global style_kismet_default
        if self.event_name:
            return '{} '.format(style_seq_event)
        else:
            return '{} '.format(style_kismet_default)

class KismetVarNode(KismetBaseRealNode):
    """
    A single Kismet variable object
    """

    def __init__(self, name, node_id, data, prev_node):
        super().__init__(name, node_id, prev_node)
        self.extra = None
        self.varname = None
        if 'seqvar_object' in name.lower():
            self.struct = data.get_struct_by_full_object(name)
            if 'ObjValue' in self.struct and self.struct['ObjValue'] != '':
                self.extra = Data.get_struct_attr_obj(self.struct, 'ObjValue')
            if 'VarName' in self.struct and self.struct['VarName'] != '':
                self.varname = self.struct['VarName']
            if not self.extra:
                self.extra = 'no object specified'

    def get_style(self):
        global style_seq_var
        return '{} '.format(style_seq_var)

    def get_label(self):
        lines = []
        if self.change_point:
            lines.append('{}.'.format(self.base_class))
        lines.append(self.short_name)
        if self.varname:
            lines.append('"{}"'.format(self.varname))
        if self.extra:
            lines.append('({})'.format(self.extra))
        return '<br/>'.join(lines)

class Kismets(object):
    """
    It's a bit stupid that these have their own class where nothing else in
    here does, but that's a side-effect of having this stuff tacked on later,
    when the rest was just procedural
    """

    def __init__(self, data, bpd_event_map, seq_event_map,
            from_bpd=None, follow_to_new_base=False,
            follow_variables=True):
        self.data = data
        self.bpd_event_map = bpd_event_map
        self.seq_event_map = seq_event_map
        self.from_bpd = from_bpd
        self.follow_to_new_base = follow_to_new_base
        self.follow_variables = follow_variables
        self.entry_points = []
        self.nodes = {}
        self.links = []
        self.unknown_events = {}

    def add_entry(self, from_id, to_name):
        self.entry_points.append((from_id, to_name))

    def follow_entries(self):
        global style_seq_event_edge
        for (idx, (from_id, entry_name)) in enumerate(self.entry_points):
            node = self.follow(entry_name, None, idx)
            if node.event_name:
                style = style_seq_event_edge
            else:
                style = None
            self.links.append((from_id, node.node_id, style, idx))

    def start_path(self, node_name):
        self.follow(node_name, None, 0)

    def follow(self, node_name, prev_node, output_idx):
        global style_event_edge
        global style_seq_event_edge
        global style_seq_var_edge
        if node_name in self.nodes:
            # already-visited nodes *should* trigger a change_point, if we
            # happen to come at them from a different angle again
            self.nodes[node_name].update_change_point(prev_node)
        else:
            node = KismetNode(node_name,
                    'kismet_node_{}'.format(len(self.nodes)),
                    self.data, prev_node,
                    self.from_bpd, self.bpd_event_map)
            self.nodes[node_name] = node

            # Follow output links
            if not prev_node or not node.change_point or self.follow_to_new_base:
                for (idx, output) in enumerate(node.output_names):
                    new_node = self.follow(output, node, idx)
                    node.links_out.add(new_node)
                    new_node.links_in.add(node)

            # Follow variables, if we're supposed to
            if self.follow_variables:
                for varname in node.variable_names:
                    if varname in self.nodes:
                        self.nodes[varname].update_change_point(node)
                    else:
                        var_id = 'kismet_var_{}'.format(len(self.nodes))
                        self.nodes[varname] = KismetVarNode(varname, var_id, data, node)
                    node.links_out.add(self.nodes[varname])
                    self.nodes[varname].links_in.add(node)
                    self.links.append((
                        node.node_id,
                        self.nodes[varname].node_id,
                        style_seq_var_edge,
                        None,
                        ))

            # Follow event links
            if node.event_link:
                if node.event_link.lower() in self.seq_event_map:
                    for remote_event_name in self.seq_event_map[node.event_link.lower()]:
                        new_node = self.follow(remote_event_name, node, 0)
                        node.links_out.add(new_node)
                        new_node.links_in.add(node)
                else:
                    if node.event_link.lower() not in self.unknown_events:
                        unknown_id = 'unknown_kismet_event_{}'.format(len(self.unknown_events))
                        unknown_node = KismetUnknownEventNode(unknown_id, node.event_link)
                        self.unknown_events[node.event_link.lower()] = unknown_node
                        self.nodes[unknown_id] = unknown_node
                    # Not adding to links_in/links_out here
                    self.links.append((
                            node.node_id,
                            self.unknown_events[node.event_link.lower()].node_id,
                            style_seq_event_edge,
                            None,
                            ))

            # Follow unspecified events (could be to BPD, could be to sequences)
            if node.to_events:
                for event_name in node.to_events:
                    found_link = False
                    event_name_lower = event_name.lower()
                    if event_name_lower in self.seq_event_map:
                        found_link = True
                        for remote_event_name in self.seq_event_map[event_link_lower]:
                            new_node = self.follow(remote_event_name, node, 0)
                            node.links_out.add(new_node)
                            new_node.links_in.add(node)
                    if self.from_bpd and event_name_lower in self.bpd_event_map:
                        found_link = True
                        for remote_event_name in self.bpd_event_map[event_name_lower]:
                            # No need to process links_in/links_out here
                            self.links.append((
                                node.node_id,
                                remote_event_name,
                                style_event_edge,
                                None,
                                ))
                    if not found_link:
                        if event_name_lower not in self.unknown_events:
                            unknown_id = 'unknown_kismet_event_{}'.format(len(self.unknown_events))
                            unknown_node = KismetUnknownEventNode(unknown_id, event_name)
                            self.unknown_events[event_name_lower] = unknown_node
                            self.nodes[unknown_id] = unknown_node
                        # Not adding to links_in/links_out here
                        self.links.append((
                                node.node_id,
                                self.unknown_events[event_name_lower].node_id,
                                style_seq_event_edge,
                                None,
                                ))

            # Follow explicit BPD links.  No need to do links_in/links_out
            # processing here.
            if node.to_behaviors:
                for (explicit_bpd_name, explicit_bpd_event) in node.to_behaviors:
                    found_link = False
                    if (self.from_bpd and
                            explicit_bpd_name.lower().startswith(self.from_bpd.lower())):
                        if explicit_bpd_event.lower() in self.bpd_event_map:
                            for explicit_inner in self.bpd_event_map[explicit_bpd_event.lower()]:
                                self.links.append((
                                    node.node_id,
                                    explicit_inner,
                                    style_event_edge,
                                    None,
                                    ))
                            found_link = True
                    if not found_link:
                        if explicit_bpd_name.lower() not in self.unknown_events:
                            unknown_id = 'unknown_kismet_event_{}'.format(len(self.unknown_events))
                            unknown_node = KismetUnknownExactBPD(unknown_id, explicit_bpd_name, explicit_bpd_event)
                            self.unknown_events[explicit_bpd_name.lower()] = unknown_node
                            self.nodes[unknown_id] = unknown_node
                        self.links.append((
                            node.node_id,
                            self.unknown_events[explicit_bpd_name.lower()].node_id,
                            style_event_edge,
                            None
                            ))

        if prev_node:
            if self.nodes[node_name].event_name:
                style = style_seq_event_edge
            else:
                style = None
            self.links.append((prev_node.node_id, self.nodes[node_name].node_id, style, output_idx))
        return self.nodes[node_name]

    def get_nodes(self):
        return self.nodes.values()

    def get_links(self):
        return self.links

    def prune_unlinked(self):
        """
        Gets rid of nodes which don't participate in any links
        """
        linked_ids = set()
        for (link_from, link_to, link_style, link_tail) in self.links:
            linked_ids.add(link_from)
            linked_ids.add(link_to)
        nodes_to_delete = []
        for name, node in self.nodes.items():
            if node.node_id not in linked_ids:
                nodes_to_delete.append(name)
        for name in nodes_to_delete:
            del self.nodes[name]

    def redo_change_points(self):
        """
        Used after loading an entire kismet Sequence - our node `change_point`
        vars are going to over-report themselves.  So loop through the nodes
        and sort it out.
        """
        # First get a list of top-level nodes and clear out change_point
        top_levels = []
        for node in self.nodes.values():
            if len(node.links_in) == 0:
                node.change_point = True
                top_levels.append(node)
            else:
                node.change_point = False

        # Recurse through top-level nodes
        new_seen = set()
        for node in top_levels:
            self.redo_change_points_recurs(new_seen, node, None)

    def redo_change_points_recurs(self, seen, new_node, prev_node):
        if new_node in seen:
            return
        else:
            seen.add(new_node)
        new_node.update_change_point(prev_node)
        for to_link in new_node.links_out:
            self.redo_change_points_recurs(seen, to_link, new_node)

###
### Functions
###

def parse_arrayindexandlength(number):
    """
    Returns an array index and length tuple for the given number.
    """
    # Could just use >> and & for this, but since we have to be more
    # careful with LinkIdAndLinkedBehavior anyway, since that one's
    # weirder, we may as well just use struct here, as well.
    number = int(number)
    byteval = struct.pack('>i', number)
    return struct.unpack('>HH', byteval)

def parse_linkidandlinkedbehavior(number):
    """
    Returns a link ID index and behavior tuple for the given number.
    """
    number = int(number)
    byteval = struct.pack('>i', number)
    (linkid, junk, behavior) = struct.unpack('>bbH', byteval)
    return (linkid, behavior)

def follow(link, cold_data, behavior_data, coming_from, seq_idx, cold_followed):
    """
    Follows the given `link` (being a compound number of the sort
    found in BPDs) through the given `behavior_data`, using `cold_data`
    as the glue.  `coming_from` is the source which we've been linked
    from.  `seq_idx` is our current BPD index.  Returns a list of tuples
    which can then be drawn.  May write out broken nodes, if any are
    found.
    """
    to_ret = []
    (link_index, link_length) = parse_arrayindexandlength(link)
    for (cold_order_idx, cold_index) in enumerate(range(link_index, link_index+link_length)):
        full_cold_index = '{}_{}'.format(seq_idx, cold_index)
        if full_cold_index in cold_followed:
            continue
        else:
            cold_followed.add(full_cold_index)
        try:
            cold = cold_data[cold_index]
        except IndexError:
            broken_id = 'broken_{}_{}'.format(seq_idx, cold_order_idx)
            print('  {} [label=<BROKEN> {}];'.format(broken_id, style_broken_cold))
            to_ret.append((coming_from, broken_id, None))
            return to_ret
        (link_id, bindex) = parse_linkidandlinkedbehavior(cold['LinkIdAndLinkedBehavior'])
        behavior = behavior_data[bindex]
        going_to = 'behavior_{}_{}'.format(seq_idx, bindex)
        delay = round(float(cold['ActivateDelay']), 6)
        if delay == 0:
            delay_extra = ''
        else:
            if int(delay) == delay:
                delay = round(delay)
            delay_extra = '<br/>d{}'.format(delay)
        to_ret.append((coming_from, going_to,
            'taillabel=<{}<br/>[{}]<br/>{}{}>'.format(cold_order_idx, cold_index, link_id, delay_extra)))
        to_ret.extend(follow(behavior['OutputLinks']['ArrayIndexAndLength'],
            cold_data,
            behavior_data,
            going_to,
            seq_idx,
            cold_followed,
            ))
    return to_ret

def get_var_list(number, cvld_data, clv_data, variable_data):
    (var_index, var_len) = parse_arrayindexandlength(number)
    var_list = []
    for cvld_idx in range(var_index, var_index+var_len):
        cvld = cvld_data[cvld_idx]
        var_name = cvld['PropertyName']
        var_type_full = cvld['VariableLinkType']
        (link_index, link_len) = parse_arrayindexandlength(cvld['LinkedVariables']['ArrayIndexAndLength'])
        # This is stupid because our ft-explorer parsing is stupid.  Doesn't really
        # handle lists of numbers too well.  We'll just pretend.
        clv_data_real = [int(p) for p in clv_data.split(',')]

        for link_index_iter in range(link_index, link_index+link_len):

            finalvar_idx = clv_data_real[link_index_iter]
            finalvar = variable_data[finalvar_idx]
            if finalvar['Name'] == '':
                finalvar_name = ''
            else:
                finalvar_name = finalvar['Name']
            if finalvar['Type'].startswith('BVAR_'):
                finalvar_type = finalvar['Type'][5:].lower()
            else:
                raise Exception('Unknown variable type: {}'.format(finalvar['Type']))

            finalvar_desc = '[{}]{}({}) via [{}]{}, [{}]'.format(
                    finalvar_idx,
                    finalvar_name.strip('"'),
                    finalvar_type,
                    cvld_idx,
                    var_name.strip('"'),
                    link_index_iter,
                    )

            if var_type_full == 'BVARLINK_Input':
                var_list.append('In: {}'.format(finalvar_desc))
            elif var_type_full == 'BVARLINK_Output':
                var_list.append('Out: {}'.format(finalvar_desc))
            elif var_type_full == 'BVARLINK_Context':
                var_list.append('Ctx: {}'.format(finalvar_desc))
            else:
                raise Exception('Unknown var type: {}'.format(var_type_full))

    return var_list

def get_var_extra(number, cvld_data, clv_data, variable_data):
    var_list = get_var_list(number, cvld_data, clv_data, variable_data)
    if len(var_list) > 0:
        return '<br/>{}'.format('<br/>'.join(var_list))
    else:
        return ''

def get_rce_bpd(rce):
    """
    Gets the BPD pointed-to by the given RemoteCustomEvent
    """
    string_build = []
    # This is actually a bit weird 'cause the output of these vars uses
    # bracket-based indexes, as if they were top-level vars, but they're
    # not.  So we're doing some special processing on 'em
    pcns = {}
    for (name, value) in rce['ProviderDefinitionPathName'].items():
        if value and value != '':
            if name.startswith('PathComponentNames['):
                pcns[int(name[19:-1])] = value.strip('"')
    for index in sorted(pcns.keys()):
        element = pcns[index]
        if len(string_build) == 0:
            string_build.append(element)
        elif (element.startswith('AIBehaviorProviderDefinition_') or 
                element.startswith('BehaviorProviderDefinition_')):
            string_build.append(':{}'.format(element))
        else:
            string_build.append('.{}'.format(element))
    return ''.join(string_build)

def generate_dot(node, bpd_name, seq_event_map, kismet_follow_class, level_name=None, show_kismet_vars=True):
    """
    Outputs a graphviz dot file from the given node
    """

    # A couple of lookup dicts for later on
    change_usability = {
            'CHANGE_Enable': 'Enable',
            'CHANGE_Disable': 'Disable',
            }
    usability_type = {
            'UT_Primary': 'primary',
            'UT_Secondary': 'secondary',
            }

    bpd_name_lower = bpd_name.lower()
    bpd = node.get_structure()
    cold_followed = set()
    event_map = {}
    label_suffix_list = []
    if level_name and level_name != '':
        label_suffix_list.append('in {}'.format(level_name))
    if kismet_follow_class:
        label_suffix_list.append('following kismets fully')
    if show_kismet_vars:
        label_suffix_list.append('showing kismet vars if applicable')
    if len(label_suffix_list) > 0:
        label_suffix = '<br/>{}'.format(', '.join(label_suffix_list))
    else:
        label_suffix = ''
    print('digraph bpd {')
    print('')
    print('  labelloc = "t";')
    print('  fontsize = 25;')
    print('  ranksep = 0.5;')
    print('  label = <{}{}>;'.format(bpd_name, label_suffix))
    print('  node [{}];'.format(style_default))
    print('')

    # First bit of processing is just if we've been handed a
    # BPD.  This used to be our only mode!  Now we support Kismet
    # stuff, too, though.

    # Some BPDs don't actually have 'BehaviorProviderDefinition' in the name!
    #if 'behaviorproviderdefinition' in bpd_name_lower:
    if 'BehaviorSequences' in bpd:

        is_bpd = True

        print('  {')
        print('    node [{}];'.format(style_event))
        for (seq_idx, seq) in enumerate(bpd['BehaviorSequences']):

            seq_name = seq['BehaviorSequenceName']
            event_data = seq['EventData2']
            behavior_data = seq['BehaviorData2']
            variable_data = seq['VariableData']
            cold_data = seq['ConsolidatedOutputLinkData']
            cvld_data = seq['ConsolidatedVariableLinkData']
            clv_data = seq['ConsolidatedLinkedVariables']

            for (event_idx, event) in enumerate(event_data):

                var_extra = get_var_extra(event['OutputVariables']['ArrayIndexAndLength'], cvld_data, clv_data, variable_data)
                event_name = event['UserData']['EventName'].strip('"')
                event_name_lower = event_name.lower()
                event_id = 'event_{}_{}'.format(seq_idx, event_idx)
                if event_name_lower not in event_map:
                    event_map[event_name_lower] = []
                event_map[event_name_lower].append(event_id)

                format_extra=''
                disabled_extra=''
                if event['UserData']['bEnabled'] != 'True':
                    format_extra=' fillcolor=gray55'
                    disabled_extra='<br/><b>(disabled)</b>'

                print('    {} [label=<[{}]{}.{}[{}]{}{}>{}];'.format(
                    event_id,
                    seq_idx,
                    seq_name.strip('"'),
                    event_name,
                    event_idx,
                    var_extra,
                    disabled_extra,
                    format_extra,
                    ))

            print('')

        print('  }')
        print('')

        event_links = []
        invalid_events = []
        remote_events = []
        seq_events = []
        unknown_events = []
        seq_event_links = []
        kismets = Kismets(data, bpd_event_map=event_map, seq_event_map=seq_event_map,
                from_bpd=bpd_name,
                follow_to_new_base=kismet_follow_class,
                follow_variables=show_kismet_vars)
        for (seq_idx, seq) in enumerate(bpd['BehaviorSequences']):

            seq_name = seq['BehaviorSequenceName']
            event_data = seq['EventData2']
            behavior_data = seq['BehaviorData2']
            variable_data = seq['VariableData']
            cold_data = seq['ConsolidatedOutputLinkData']
            cvld_data = seq['ConsolidatedVariableLinkData']
            clv_data = seq['ConsolidatedLinkedVariables']

            for (behavior_idx, behavior) in enumerate(behavior_data):
                if behavior['Behavior'] != 'None':
                    (behavior_type, full_behavior_class, junk) = behavior['Behavior'].split("'", 2)
                    if full_behavior_class.lower().startswith(bpd_name_lower):
                        behavior_class = full_behavior_class[len(bpd_name_lower)+1:]
                    else:
                        behavior_class = full_behavior_class
                else:
                    behavior_type = ''
                    behavior_class = 'None'
                    full_behavior_class = 'None'

                var_extra = get_var_extra(behavior['LinkedVariables']['ArrayIndexAndLength'], cvld_data, clv_data, variable_data)
                behavior_id = 'behavior_{}_{}'.format(seq_idx, behavior_idx)

                # Load some extra data, depending on the behavior type.  This
                # is also where we'll link up to kismet or other BPD events
                behavior_extra = ''

                # Get some info for ChangeInstanceDataSwitch
                if behavior_type == 'Behavior_ChangeInstanceDataSwitch':
                    bs = data.get_struct_by_full_object(full_behavior_class)
                    behavior_extra = '<br/>{} -&gt; {}'.format(
                            bs['SwitchName'],
                            bs['NewValue'],
                            )

                # Get some info for IsSequenceEnabled
                elif behavior_type == 'Behavior_IsSequenceEnabled':
                    bs = data.get_struct_by_full_object(full_behavior_class)
                    behavior_extra = '<br/>"{}"'.format(
                            bs['SequenceName'],
                            )

                # Get some info for ChangeUsability
                elif behavior_type == 'Behavior_ChangeUsability':
                    bs = data.get_struct_by_full_object(full_behavior_class)
                    behavior_extra = '<br/>({} {})'.format(
                            change_usability.get(bs['ChangeUsability'], bs['ChangeUsability']),
                            usability_type.get(bs['UsabilityType'], bs['UsabilityType']),
                            )

                # Get some info for Delay
                elif behavior_type == 'Behavior_Delay':
                    bs = data.get_struct_by_full_object(full_behavior_class)
                    delayval = bs['Delay'].rstrip('0')
                    if delayval[-1] == '.':
                        delayval = delayval[:-1]
                    behavior_extra = '<br/>(delay: {})'.format(delayval)

                # Get some info for ChangeRemoteBehaviorSequenceState
                elif behavior_type == 'Behavior_ChangeRemoteBehaviorSequenceState':
                    try:
                        bs = data.get_struct_by_full_object(full_behavior_class)
                        behavior_extra = '<br/>({} {})'.format(
                                change_usability.get(bs['Action'], bs['Action']),
                                bs['SequenceName'],
                                )
                    except KeyError:
                        # TPS has at least one case where this fails, in
                        # GD_Prototype_Skills.Projectiles.Projectile_SpawnSecondWindClone:BehaviorProviderDefinition_0
                        # Really we should probably check this everywhere, but 
                        # generate_all_dots.py should do.
                        pass

                # Get some info for SimpleAnimPlay and SimpleAnimStop
                elif behavior_type == 'Behavior_SimpleAnimPlay' or behavior_type == 'Behavior_SimpleAnimStop':
                    bs = data.get_struct_by_full_object(full_behavior_class)
                    behavior_extra = '<br/>{}'.format(bs['AnimName'])

                # We can draw some more links if we're a remotecustomevent
                elif behavior_type == 'Behavior_RemoteCustomEvent':
                    rce = data.get_struct_by_full_object(full_behavior_class)
                    if rce:
                        rce_bpd = get_rce_bpd(rce)
                        event_name = rce['CustomEventName']
                        behavior_extra = '<br/>"{}"'.format(event_name)
                        if rce_bpd.lower() == bpd_name_lower:
                            if event_name.lower() in event_map:
                                for event_id in event_map[event_name.lower()]:
                                    event_links.append((behavior_id, event_id))
                            else:
                                invalid_event_name_id = 'invalid_event_{}'.format(len(invalid_events))
                                invalid_events.append((invalid_event_name_id, event_name))
                                event_links.append((behavior_id, invalid_event_name_id))
                        else:
                            really_remote_id = 'really_remote_id_{}'.format(len(remote_events))
                            remote_events.append((really_remote_id, rce_bpd, event_name))
                            event_links.append((behavior_id, really_remote_id))

                # Handle CustomEvents and RemoteEvents.  Functionally these appear to be nearly
                # identical, as far as BL2+TPS's datasets are concerned.  RemoteEvents in our
                # datasets seem to only ever link to seqvar event names, and don't seem to ever
                # link back to BPD event names, whereas CustomEvents can.  Contrariwise,
                # CustomEvents nearly always seem to link to the same BPD or to other BPDs, and
                # rarely to seqvar event names (though it does seem to do that sometimes).
                # Ayway, we may as well just check for both.  Note that currently we don't
                # handle linking to remote BPDs, but if we have a level specified, we may be
                # able to follow into seqvar events.
                elif behavior_type == 'Behavior_CustomEvent' or behavior_type=='Behavior_RemoteEvent':
                    if behavior_type == 'Behavior_CustomEvent':
                        attr_name = 'CustomEventName'
                    else:
                        attr_name = 'EventName'
                    rce = data.get_struct_by_full_object(full_behavior_class)
                    if rce:
                        event_name = rce[attr_name]
                        behavior_extra = '<br/>"{}"'.format(event_name)
                        event_name_lower = event_name.lower()
                        got_a_link = False
                        # First check for any links within the same BPD
                        if event_name_lower in event_map:
                            got_a_link = True
                            for event_id in event_map[event_name_lower]:
                                event_links.append((behavior_id, event_id))
                        # Now for any links outside (will probably never happen)
                        if event_name_lower in seq_event_map:
                            got_a_link = True
                            for seq_obj in seq_event_map[event_name_lower]:
                                #seq_id = 'seq_id_{}'.format(len(seq_events))
                                #seq_events.append((seq_id, seq_obj))
                                #seq_event_links.append((behavior_id, seq_id))
                                kismets.add_entry(behavior_id, seq_obj)
                        # If we haven't found any links, put the event name out there,
                        # at least.
                        if not got_a_link:
                            unknown_event_id = 'unknown_event_id_{}'.format(len(unknown_events))
                            unknown_events.append((unknown_event_id, event_name))
                            seq_event_links.append((behavior_id, unknown_event_id))

                # Finally, draw out the node
                print('  {} [label=<[{}] {}{}{}>];'.format(
                    behavior_id,
                    behavior_idx,
                    behavior_class,
                    behavior_extra,
                    var_extra,
                    ))

            print('')

        # Loop through Kismet sequence data, if we've colleceted any
        kismets.follow_entries()

        if len(invalid_events) > 0:
            print('  {')
            print('    node [{}];'.format(style_event_invalid))
            for (node_id, event_name) in invalid_events:
                print('    {} [label=<{}<br/>(possibly invalid?)>];'.format(node_id, event_name))
            print('  }')
            print('')

        if len(remote_events) > 0:
            print('  {')
            print('    node [{}];'.format(style_event_remote))
            for (node_id, remote_bpd, event_name) in remote_events:
                if ':' in remote_bpd:
                    (first, second) = remote_bpd.split(':', 1)
                    print('    {} [label=<{}:<br/>{}<br/>{}>];'.format(node_id, first, second, event_name))
                else:
                    print('    {} [label=<{}<br/>{}>];'.format(node_id, remote_bpd, event_name))
            print('  }')
            print('')

        if len(unknown_events) > 0:
            print('  {')
            print('    node [{}];'.format(style_event_unknown))
            for (node_id, event_name) in unknown_events:
                if len(seq_event_map) == 0:
                    extra_label = ',<br/>or to an unknown SeqEvent'
                else:
                    extra_label = ''
                print('    {} [label=<{}<br/><i>(Unknown Event,<br/>may call to other BPD{})</i>>];'.format(node_id, event_name, extra_label))
            print('  }')
            print('')

        if len(event_links) > 0:
            print('  {')
            print('    edge [{}];'.format(style_event_edge))
            for (link_from, link_to) in event_links:
                print('    {} -> {};'.format(link_from, link_to))
            print('  }')
            print('')

        if len(seq_event_links) > 0:
            print('  {')
            print('    edge [{}];'.format(style_seq_event_edge))
            for (link_from, link_to) in seq_event_links:
                print('    {} -> {};'.format(link_from, link_to))
            print('  }')
            print('')

        bpd_links = []
        for (seq_idx, seq) in enumerate(bpd['BehaviorSequences']):

            seq_name = seq['BehaviorSequenceName']
            event_data = seq['EventData2']
            behavior_data = seq['BehaviorData2']
            variable_data = seq['VariableData']
            cold_data = seq['ConsolidatedOutputLinkData']
            cvld_data = seq['ConsolidatedVariableLinkData']
            clv_data = seq['ConsolidatedLinkedVariables']

            for (event_idx, event) in enumerate(event_data):
                bpd_links.extend(follow(event['OutputLinks']['ArrayIndexAndLength'],
                        cold_data,
                        behavior_data,
                        'event_{}_{}'.format(seq_idx, event_idx),
                        seq_idx,
                        cold_followed))

        print('')

        # Now actually draw the BPD edges.  Doing these at the end so I can style
        # them all at once
        if len(bpd_links) > 0:
            print('  {')
            print('    edge [{}];'.format(style_bpd_edge))
            for (from_behavior, to_behavior, label) in bpd_links:
                if label:
                    label = ' [{}]'.format(label)
                else:
                    label = ''
                print('    {} -> {}{};'.format(from_behavior, to_behavior, label))
            print('  }')
            print('')

    else:

        # Here's our branch if we're just doing a Kismet tree
        is_bpd = False

        # Set up a Kismets object, no matter what we do
        kismets = Kismets(data, bpd_event_map=event_map,
                seq_event_map=seq_event_map,
                follow_to_new_base=kismet_follow_class,
                follow_variables=show_kismet_vars)

        # Check to see if we've been passed a "bare" sequence object
        root_node = data.get_node_by_full_object(bpd_name)
        root_struct = root_node.get_structure()
        if 'SequenceObjects' in root_struct:
            for child_name, child in root_node.children.items():
                full_child_name = '{}.{}'.format(bpd_name, child.name)
                if full_child_name not in kismets.nodes:
                    child_struct = child.get_structure()
                    # This check is here to skip things which aren't SequenceOp objects
                    if 'bIsCurrentDebuggerOp' in child_struct:
                        kismets.start_path(full_child_name)
            kismets.prune_unlinked()
            kismets.redo_change_points()
        else:
            # Okay, we just (presumably) got an individual Sequence item.
            # Recurse into it and be done!
            kismets.start_path(bpd_name)

    # Kismet stuff gets rendered regardless, since BPDs will be able to
    # recurse into them.

    kismet_nodes = kismets.get_nodes()
    if len(kismet_nodes) > 0:
        for node in kismet_nodes:
            print('  {} [{}label=<{}>];'.format(node.node_id, node.get_style(), node.get_label()))
        print('')

    kismet_links = kismets.get_links()
    if len(kismet_links) > 0:
        for (link_from, link_to, link_style, link_tail) in kismet_links:
            styles = []
            if link_style:
                styles.append(link_style)
            if link_tail is not None:
                styles.append('taillabel=<{}>'.format(link_tail))
            if len(styles) > 0:
                style_str = ' [{}]'.format(' '.join(styles))
            else:
                style_str = ''
            print('  {} -> {}{};'.format(link_from, link_to, style_str))
        print('')

    print('')
    print('}')

###
### Now process to find out what we're supposed to do
###

if __name__ == '__main__':

    if 'generate_all_dots' in sys.argv[0]:

        ###
        ### Generate all possible graphviz dot files (really only used for
        ### my own debugging)
        ###

        dotdir = 'dotfiles'

        if not os.path.exists(dotdir) and not os.path.isdir(dotdir):
            print('ERROR: "{}" directory must exist, closing.'.format(dotdir))
            sys.exit(1)

        bl2_start_from = 0
        tps_start_from = 0
        if len(sys.argv) > 1:
            try:
                bl2_start_from = int(sys.argv[1])
            except ValueError:
                pass
        if len(sys.argv) > 2:
            try:
                tps_start_from = int(sys.argv[2])
            except ValueError:
                pass

        if bl2_start_from == 0 and tps_start_from == 0:
            print('About to generate dotfiles for ALL BPDs in both BL2 and TPS.')
        else:
            print('About to generate dotfiles for BPDs in both BL2 and TPS.')
            print('  BL2 start: {}'.format(bl2_start_from))
            print('  TPS start: {}'.format(tps_start_from))
        print('Ctrl-C now if that\'s not what you want.')
        print('')
        print('(Hit a key to continue)')
        sys.stdin.readline()

        bpd_blacklist = set([
            # With our DLC5 update, these BPDs seem to reference some objects which can't be dumped.
            # Need to verify that this has actually changed, or just a weird dump error...
            'GD_Orchid_CrystaliskAqua.Character.AIDef_Orchid_CrystaliskAqua:AIBehaviorProviderDefinition_1',
            'GD_Orchid_CrystaliskAqua.HitRegions.HitRegion_B_FootCrystalAqua:BehaviorProviderDefinition_0',
            'GD_Orchid_CrystaliskAqua.HitRegions.HitRegion_L_FootCrystalAqua:BehaviorProviderDefinition_0',
            'GD_Orchid_CrystaliskAqua.HitRegions.HitRegion_R_FootCrystalAqua:BehaviorProviderDefinition_0',
            'GD_Orchid_PirateQueen_Combat.Character.AIDef_Orchid_PirateQueen_Combat:AIBehaviorProviderDefinition_1',
            'GD_Sage_SM_BigFeetData.Creature.Character.AIDef_Sage_BigFeet_Creature:AIBehaviorProviderDefinition_1',
            ])

        generated = 0
        for (game, start_from) in [('BL2', bl2_start_from), ('TPS', tps_start_from)]:

            if start_from != -1:

                data = Data(game)

                objects = []
                objects.extend(data.get_all_by_type('AIBehaviorProviderDefinition'))
                objects.extend(data.get_all_by_type('BehaviorProviderDefinition'))

                max_len_seen = 0
                for (idx, bpd_name) in enumerate(sorted(objects)[start_from:]):
                    if bpd_name in bpd_blacklist:
                        continue
                    with open('{}/{}_{}.dot'.format(dotdir, game, bpd_name), 'w') as df:

                        # Redirect stdout.  This is hokey, but whatever.
                        sys.stdout = df

                        # Figure out out string to report to the user
                        report_str = 'Processing {} #{} - {}'.format(game, idx+start_from, bpd_name)
                        if len(report_str) > 120:
                            report_str = '{}...'.format(report_str[:117])
                        if len(report_str) > max_len_seen:
                            max_len_seen = len(report_str)
                            spaces = ''
                        else:
                            spaces = ' '*(max_len_seen-len(report_str))
                        sys.stderr.write("{}{}\r".format(report_str, spaces))

                        # Load the node, complaining if we couldn't find it
                        node = data.get_node_by_full_object(bpd_name)
                        if not node:
                            print('', file=sys.stderr)
                            print('ERROR: {} {} not found'.format(game, bpd_name), file=sys.stderr)

                        # aaaand generate.
                        try:
                            generate_dot(node, bpd_name, {}, False)
                            generated += 1
                        except Exception as e:
                            print('', file=sys.stderr)
                            raise e

        print('', file=sys.stderr)
        print('', file=sys.stderr)
        print('{} dotfiles generated'.format(generated), file=sys.stderr)

    else:

        ###
        ### Main application - generate a single graphviz dot file, to STDOUT.
        ###

        parser = argparse.ArgumentParser(
            description='Generate a graphviz DOT file showing a borderlands BPD',
            )

        parser.add_argument('-l', '--level',
            required=False,
            help="Optional level in which the BPD is running, to link in sequence data too",
            )

        parser.add_argument('-f', '--follow',
            action='store_true',
            help="Follow Kismet sequences through to other classes (won't do anything without --level as well)",
            )

        parser.add_argument('-v', '--vars',
            dest='kismet_vars',
            action='store_true',
            help="Show Kismet variables as nodes in graphs",
            )

        parser.add_argument('game',
            choices=['bl2', 'tps'],
            help='Which game to search',
            )

        parser.add_argument('bpd',
            help='BPD to output',
            )

        args = parser.parse_args()

        game = args.game.upper()
        bpd_name = args.bpd

        # Load in our sequence event map, if we can
        seq_event_map = {}
        if args.level and args.level != '':
            if args.level.lower() not in level_sequence_event_names[game]:
                raise argparse.ArgumentTypeError('Level name {} not found in {}'.format(args.level, game))
            seq_event_map = level_sequence_event_names[game][args.level.lower()]

        # Initialize data
        data = Data(game)

        # Get the actual node
        try:
            node = data.get_node_by_full_object(bpd_name)
            if not node:
                print('ERROR: {} could not be found'.format(bpd_name), file=sys.stderr)
                sys.exit(2)
        except Exception as e:
            print('ERROR: {} could not be loaded: {}'.format(bpd_name, str(e)))
            sys.exit(2)

        # Get a label to use for the level name
        english_level_label = None
        if args.level and args.level != '':
            english_level_name = data.get_level_name(args.level)
            if english_level_name:
                english_level_label = '{} ({})'.format(english_level_name, args.level)
            else:
                english_level_label = args.level

        # This is silly, should have a dict to look this up
        generate_dot(node, bpd_name, seq_event_map, args.follow, level_name=english_level_label, show_kismet_vars=args.kismet_vars)
