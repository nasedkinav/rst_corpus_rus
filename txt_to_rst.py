import os
import re
import string
import sys

from pymorphy2 import MorphAnalyzer

os.environ['TAGDIR'] = '/Users/nasedkinav/Documents/study/comp_ling/comp_ling/tree_tagger/'  # locate treetagger
from rusclasp import Splitter

RELATIONS = {
    'rst': [
        'antithesis',
        'attribution',
        'attribution1',
        'attribution2',
        'background',
        'cause-effect',
        'concession',
        'conclusion',
        'condition',
        'elaboration',
        'evaluation',
        'evidence',
        'interpretation-evaluation',
        'interpretation',
        'motivation',
        'non_volitional_cause',
        'non_volitional_effect',
        'preparation',
        'purpose',
        'solutionhood',
        'volitional_cause',
        'volitional_effect'
    ],
    'multinuc': [
        'comparison',
        'contrast',
        'joint',
        'restatement',
        'same-unit',
        'sequence'
    ]
}

PARAGRAPH_DELIMITER = '#####'
DEFAULT_SEGMENT_RELATION = 'antithesis'
SPLITTER = Splitter()
MORPH = MorphAnalyzer()
INSERTED = {}
SPACES = re.compile('\s{2,}')
STARTS_WITH_WHAT = re.compile('^что\W')
DASHES = re.compile('–\W.*\W–')


def load_inserted():
    global INSERTED

    if not len(INSERTED):
        with open('inserted') as ins:
            INSERTED = {l.strip(): None for l in ins.readlines()}


def get_relations(edu, edu_lemma):
    rel = []

    i = 0
    while i < len(edu):
        r = None
        has_next = i + 1 < len(edu)

        tokens = edu_lemma[i].split()
        if tokens[-1] in ['надеяться', 'опасаться', 'отметить', 'отмечать', 'сообщаться', 'утверждать', 'заявить', 'заявлять'] \
                and has_next and STARTS_WITH_WHAT.match(edu_lemma[i + 1]):
            r = [i, i + 1, 'attribution']

        elif tokens[-1] in ['передать', 'передавать', 'подчеркнуть', 'подчеркивать'] \
                and has_next and STARTS_WITH_WHAT.match(edu_lemma[i + 1]) \
                and (not edu[i][0].isupper() or len(edu[i].split()) > 1):
            r = [i, i + 1, 'attribution']

        elif tokens[-1] in ['написать', 'рассказать', 'рассказывать', 'сообщить', 'сообщать', 'сказать']:
            r = [i, i + 1, 'attribution']

        elif i > 0 and len(tokens) > 2 and tokens[0] == 'о' and tokens[1] == 'это' \
                and tokens[2] in ['сообщать', 'сообщаться', 'сообщить', 'писать', 'написать'] \
                and not edu[i].startswith('Об'):
            r = [i, i - 1, 'attribution']

        elif tokens[-1] == 'настолько' and has_next and STARTS_WITH_WHAT.match(edu_lemma[i + 1]):
            r = [i, i + 1, 'cause-effect']

        elif i > 0 and tokens[0] == 'поскольку' and not edu[i].startswith('Поскольку'):
            r = [i, i - 1, 'cause-effect']

        elif ' '.join(tokens[-3:]) == 'являться причина тот' and has_next and STARTS_WITH_WHAT.match(edu_lemma[i + 1]):
            r = [i, i + 1, 'cause-effect']

        elif i > 0 and (' '.join(tokens[:3]) == 'в результат что' or ' '.join(tokens[:4]) == 'в связь с что'
                        or ' '.join(tokens[:2]) == 'вследствие что') and not edu[i].startswith('В'):
            r = [i, i - 1, 'cause-effect']

        elif i > 0 and (' '.join(tokens[:2]) == 'из-за что' or ' '.join(tokens[:3]) == 'из за что') and not edu[i].startswith('Из'):
            r = [i, i - 1, 'cause-effect']

        elif i + 2 < len(edu) and edu[i].startswith('Несмотря') \
                and ' '.join(tokens[0:3]) == 'несмотря на то' and STARTS_WITH_WHAT.match(edu_lemma[i + 1]):
            r = [i, i + 2, 'concession']

        elif i > 0 and not edu[i].startswith('Несмотря') \
                and ' '.join(tokens[-3:]) == 'несмотря на то' and i + 2 == len(edu) and STARTS_WITH_WHAT.match(edu_lemma[i + 1]):
            r = [i, i - 1, 'concession']

        elif 'пока' in tokens and has_next:
            r = [i, i + 1, 'condition']

        elif tokens[0] == 'если' and has_next and edu[i].startswith('Если'):
            r = [i, i + 1, 'condition']

        elif tokens[0] == 'если' and i > 0 and not edu[i].startswith('Если'):
            r = [i, i - 1, 'condition']

        elif tokens[0] == 'если' and has_next:
            for j in range(i + 1, len(edu)):
                if edu[j].startswith('то') and edu[j].split(' ').strip(string.punctuation) == 'то':
                    r = [i, j, 'condition']
                    break

        elif i > 0 and ' '.join(tokens[:2]) == 'вместо что':
            r = [i, i - 1, 'contrast']

        elif i > 0 and (tokens[0] == 'который' or len(tokens) > 1 and tokens[1] == 'который' and MORPH.parse(tokens[0])[0].tag.POS == 'PREP'):
            r = [i, i - 1, 'elaboration']

        elif i > 0 and ' '.join(tokens[0:3]) == 'параллельно с это':
            r = [i, i - 1, 'joint']

        elif tokens[0] == 'чтобы' and edu[i].startswith('Чтобы') and has_next:
            r = [i, i + 1, 'purpose']

        elif i > 0 and tokens[0] == 'чтобы' and not edu[i].startswith('Чтобы'):
            r = [i, i - 1, 'purpose']

        if r:
            rel.append(r)

        i += 1

    return rel


def get_splitting_relations(edu, edu_lemma):
    rel = []

    i = 0
    while i < len(edu):
        r = None

        tokens = edu_lemma[i].split()

        if 'объявить о' in edu_lemma[i] or 'объявлять о' in edu_lemma[i]:
            for j, t in enumerate(tokens):
                if j + 2 < len(tokens) and t in ['объявить', 'объявлять'] and tokens[j + 1] == 'о':
                    # split initial edu
                    edu_i_split = edu[i].split()
                    edu = edu[:i] + [' '.join(edu_i_split[:j + 2]), ' '.join(edu_i_split[j + 2:])] + edu[i + 1:]
                    # split corresponding edu_lemma in the same place
                    edu_lemma = edu_lemma[:i] + [' '.join(tokens[:j + 2]), ' '.join(tokens[j + 2:])] + edu_lemma[i + 1:]
                    # proceed relation
                    r = [i, i + 1, 'attribution']
                    break

        elif i + 2 < len(edu) and edu[i].strip(string.punctuation) == 'Для того' and edu[i + 1].startswith('чтобы'):
            edu = edu[:i] + [' '.join([edu[i], edu[i + 1]])] + edu[i + 2:]
            edu_lemma = edu_lemma[:i] + [' '.join([edu_lemma[i], edu_lemma[i + 1]])] + edu_lemma[i + 2:]
            r = [i, i + 1, 'purpose']

        elif i + 1 < len(edu) and len(tokens) > 2 and edu[i].strip(string.punctuation).endswith('для того') \
                and edu[i + 1].startswith('чтобы'):
            # split edu[i] on 'для того' and merge it part with next clause
            split_ind = edu[i].rfind('для того') - 1
            split_ind_lemma = edu_lemma[i].rfind('для тот') - 1
            edu = edu[:i] + [edu[i][:split_ind], ' '.join([edu[i][split_ind + 1:], edu[i + 1]])] + edu[i + 2:]
            edu_lemma = edu_lemma[:i] + [edu_lemma[i][:split_ind_lemma], ' '.join([edu_lemma[i][split_ind_lemma + 1:], edu_lemma[i + 1]])] + edu_lemma[i + 2:]
            r = [i + 1, i, 'purpose']

        elif DASHES.search(edu[i]):
            l, r = DASHES.search(edu[i]).span()
            edu = edu[:i] + [edu[i][:l - 1], edu[i][l:r], edu[i][r + 1:]] + edu[i + 1:]
            l, r = DASHES.search(edu_lemma[i]).span()
            edu_lemma = edu_lemma[:i] + [edu_lemma[i][:l - 1], edu_lemma[i][l:r], edu_lemma[i][r + 1:]] + edu_lemma[i + 1:]
            r = [i + 1, i, 'elaboration']
            i += 1  # skip created dashed edu

        if r:
            rel.append(r)

        i += 1

    return edu, edu_lemma, rel


def transform_file(path):
    with open(path) as f:
        text = f.readlines()

    # pre-load dictionaries
    load_inserted()

    total_edu = []
    total_rel = {'rst': [], 'multinuc': []}
    # each line is treated as a paragraph
    for i, line in enumerate(text):
        if not line.strip():
            continue

        split = SPLITTER.split(SPACES.sub(' ', line))

        edus = [[item[2][0][0], item[2][0][1] + 1] for item in split['entities']]
        same_unit = [[int(item[2][0][1][1:]) - 1, int(item[2][1][1][1:]) - 1] for item in split['relations']]
        boundaries = [e[1] for e in edus[:-1]]  # skip last edu, there is no need in paragraph-end boundary

        # remove inserted clauses
        j = 0
        while j < len(edus):
            if split['text'][edus[j][0]:edus[j][1]].strip(string.punctuation).lower() in INSERTED:
                if j == len(edus) - 1:
                    # if it is the last edu in paragraph, merge it with previous (remove last boundary)
                    boundaries.pop()
                else:
                    # remove the right boundary
                    boundaries.remove(edus[j][1])
                    # if rusclasp says that next and previous clauses are same-unit, remove left boundary too
                    if [j - 1, j + 1] in same_unit:
                        boundaries.remove(edus[j - 1][1])
                        j += 1  # skip next edu
            j += 1

        # form new edus
        edus = [[0, 0]]
        for j, b in enumerate(boundaries):
            edus[j][1] = b
            edus.append([b + 1, 0])
        edus[-1][1] = len(split['text'])

        # format text edus
        par_edu = [split['text'][e[0]:e[1]].strip() for e in edus if e[1] - e[0] > 0 and split['text'][e[0]:e[1]].strip()]
        par_edu_lemmatized = [' '.join([MORPH.parse(token.strip(string.punctuation))[0].normal_form.replace('ё', 'е')
                                        for token in e.split()]).strip() for e in par_edu]

        # retrieve relations that split initial clauses
        par_edu, par_edu_lemmatized, rel = get_splitting_relations(par_edu, par_edu_lemmatized)

        # retrieve relations according to the final distribution
        rel += get_relations(par_edu, par_edu_lemmatized)

        # update relations indices according to total segments
        segment_offset = len(total_edu)
        for r in rel:
            r[0] += segment_offset
            r[1] += segment_offset
            if r[2] in RELATIONS['rst']:
                total_rel['rst'].append(r)
            else:
                total_rel['multinuc'].append(r)

        par_edu[0] = '%s %s' % (PARAGRAPH_DELIMITER, par_edu[0])  # append paragraph delimiter
        total_edu += par_edu

    rel_str = ""
    for typ, rel in RELATIONS.items():
        for r in rel:
            rel_str += """\n\t\t\t<rel name="%s" type="%s" />""" % (r, typ)

    # create segments and groups
    segments = [{'text': edu, 'parent': None, 'relname': DEFAULT_SEGMENT_RELATION} for edu in total_edu]
    for i, parent, relname in total_rel['rst']:
        segments[i]['parent'] = parent
        segments[i]['relname'] = relname

    groups = []
    for i, neighbour, relname in total_rel['multinuc']:
        if segments[i]['parent'] is None and segments[neighbour]['parent'] is None:
            groups.append(len(segments) if not groups else groups[-1] + 1)
            segments[i]['parent'] = segments[neighbour]['parent'] = groups[-1]
            segments[i]['relname'] = segments[neighbour]['relname'] = relname

    seg_str = ""
    for i, s in enumerate(segments):
        seg_str += """\n\t\t<segment id="%s"%s relname="%s">%s</segment>""" % (
            i + 1,
            (' parent="%s"' % (s['parent'] + 1)) if s['parent'] is not None else '',
            s['relname'],
            s['text']
        )
    for g in groups:
        seg_str += """\n\t\t<group id="%s" type="multinuc" relname="%s"/>""" % (g + 1, DEFAULT_SEGMENT_RELATION)

    res = """<rst>
    <header>
        <relations>%s
        </relations>
    </header>
    <body>%s
    </body>
</rst>""" % (rel_str, seg_str)

    return res


if __name__ == '__main__':
    if len(sys.argv) != 2 or not os.path.exists(sys.argv[1]):
        sys.exit("You should provide path to directory where txt files to be converted are located")

    for file_name in os.listdir(sys.argv[1]):
        if not file_name.endswith('.txt'):
            continue
        print("Processing '%s'" % file_name)

        xml = transform_file(os.path.join(sys.argv[1], file_name))
        with open(os.path.join('edu_split_with_rel', os.path.splitext(file_name)[0] + '.rs3'), mode='wb') as of:
            of.write(xml.encode('utf-8'))
