# Description of metric calculation (paragraph C): http://web.asc.upenn.edu/usr/krippendorff/mwebreliability5.pdf
import os
import xmltodict
import sys

from collections import defaultdict


def parse_relations(path, debug=False):
    tree = xmltodict.parse(open(path, mode='rb'), encoding='utf-8')

    segment_id = set()
    group_id = set()
    nodes = {}

    edge_parent_to_child = defaultdict(list)
    edge_child_to_parent = defaultdict(int)  # only one parent permitted, assume that there is no zero id

    # process segments
    for s in tree['rst']['body']['segment']:
        _id = int(s['@id'])
        parent = int(s['@parent']) if '@parent' in s else None

        segment_id.add(_id)
        nodes[_id] = {
            'relname': s['@relname'] if parent else None,  # relation
            'text': s['#text'] if '#text' in s else '',  # edu text
            'covered_segments': set()  # id of child segments
        }
        if parent:
            edge_parent_to_child[parent].append(_id)
            edge_child_to_parent[_id] = parent

    # process groups
    for g in tree['rst']['body']['group']:
        _id = int(g['@id'])
        parent = int(g['@parent']) if '@parent' in g else None

        group_id.add(_id)
        nodes[_id] = {
            'relname': g['@relname'] if parent else None,  # relation
            'type': g['@type'],
            'covered_segments': set()  # id of child segments
        }
        if parent:
            edge_parent_to_child[parent].append(_id)
            edge_child_to_parent[_id] = parent

    total_id = segment_id.union(group_id)

    # gather covered segments for each node in bottom-up search
    queue = [_id for _id in total_id if not edge_parent_to_child[_id]]  # start with leaf nodes
    while queue:
        node = queue.pop(0)
        if edge_child_to_parent[node]:
            parent_id = edge_child_to_parent[node]
            # proceed covered segments of current node to its parent
            nodes[parent_id]['covered_segments'].update(nodes[node]['covered_segments'])
            if node in segment_id:
                # if current node is a segment, proceed it to its parent too
                nodes[parent_id]['covered_segments'].add(node)
            queue.append(parent_id)

    # gather relations
    root = [_id for _id in total_id if not edge_child_to_parent[_id]]
    rel_types = {r['@name']: r['@type'] for r in tree['rst']['header']['relations']['rel']}
    relations = {}
    for _id, n in nodes.items():
        rel_name = n['relname']
        if _id in root or rel_name == 'span':
            # root nodes cannot have a parent relation
            # spans are not taken into account
            continue

        if rel_types[rel_name] == 'multinuc':
            # if we found one part from multi-nuclear relation find the rest and form one relation
            # each part should proceed same relation key, so that further loops do not make any copy
            parent_id = edge_child_to_parent[_id]
            # loop through closest children and retrieve only with same relation
            multi_ss = set()
            for child in edge_parent_to_child[parent_id]:
                if nodes[child]['relname'] != rel_name:
                    raise Exception("Undefined relation '%s' under multi-nuclear group %s" % (nodes[child]['relname'], parent_id))
                # for group get all covered segments, for segment - only it
                multi_ss.update(nodes[child]['covered_segments'] if child in group_id else {child})

            str_multi = ' '.join([nodes[s]['text'] for s in sorted(multi_ss)])
            relations['multi: %s' % str_multi] = rel_name

        elif rel_types[rel_name] == 'rst':
            # for group get all covered segments, for segment - only it
            ss = n['covered_segments'] if _id in group_id else {_id}
            str_from = ' '.join([nodes[s]['text'] for s in sorted(ss)])

            parent_id = edge_child_to_parent[_id]
            parent = nodes[parent_id]
            # for group get all covered segments, for segment - only it
            parent_ss = parent['covered_segments'] if parent_id in group_id else {parent_id}
            parent_ss.difference_update(ss)  # exclude current node covered segments
            str_to = ' '.join([nodes[s]['text'] for s in sorted(parent_ss)])

            relations['from: %s\nto: %s' % (str_from, str_to)] = rel_name
        else:
            raise Exception("Undefined relation name '%s'" % rel_name)

    if debug:
        for rel_name, rel_type in relations.items():
            print('%s\nrel: %s\n' % (rel_name, rel_type))
        print(len(relations))

    return relations


def calculate_alpha(path):
    distinct_rel_type = set()
    units = defaultdict(dict)       # reliability data matrix
    annotations = os.listdir(path)  # distinct annotations

    for a in annotations:
        for u_key, rel_name in parse_relations(os.path.join(path, a)).items():
            units[u_key][a] = rel_name
            distinct_rel_type.add(rel_name)

    distinct_rel_type = sorted(distinct_rel_type)

    # count number of annotators within unit
    for u_key, u_data in units.items():
        units[u_key]['m'] = len(u_data.keys())

    # coincidences matrix
    coincidences = defaultdict(dict)
    for r1 in distinct_rel_type:
        for r2 in distinct_rel_type:
            if r2 not in coincidences[r1]:
                # assign default value
                coincidences[r1][r2] = 0

            # loop through each unit and count the number of pairs (r1, r2) available in annotators codes
            for u_key, u_data in units.items():
                if u_data['m'] < 2:
                    # no comparison in such cases
                    continue

                if r1 == r2:
                    # in case of same value the result count is n(n-1)/2 where n is number of value occurrences in unit
                    # division by 2 because each pair (r1, r2) and (r2, r1) contributes the half of possible pairs
                    n = len([u_data[a] for a in annotations if a in u_data and u_data[a] == r1])
                    cnt = float(n * (n - 1)) / 2
                else:
                    # in case of distinct values the resulting count is c1 * c2
                    # where c1 is count of r1 occurrences, and c2 is count of r2 occurrences
                    c1 = len([u_data[a] for a in annotations if a in u_data and u_data[a] == r1])
                    c2 = len([u_data[a] for a in annotations if a in u_data and u_data[a] == r2])
                    cnt = float(c1 * c2)

                if cnt:
                    coincidences[r1][r2] += cnt / (u_data['m'] - 1)

    diagonal_sum = sum([coincidences[r][r] for r in distinct_rel_type])
    row_sums = {r: sum(coincidences[r].values()) for r in distinct_rel_type}
    n = sum(row_sums.values())
    chance_agreement_numerator = sum([row_sums[r] * (row_sums[r] - 1) for r in distinct_rel_type])

    alpha = float((n - 1) * diagonal_sum - chance_agreement_numerator) / (n * (n - 1) - chance_agreement_numerator)

    print('\n'.join(annotations + ["Alpha: %.6f" % alpha]))


if __name__ == '__main__':
    if len(sys.argv) < 2 or sum([os.path.exists(path) for path in sys.argv[1:]]) != len(sys.argv) - 1:
        sys.exit("You should provide path to the directories where annotations to be analysed are located")

    for _dir in sys.argv[1:]:
        calculate_alpha(_dir)
