#!/usr/bin/env python
# encoding: utf-8

import codecs
import itertools
import json
import os
import re
import sys
import stopwords
from collections import defaultdict

debug = True
all_chunks = {}

# From https://en.wikibooks.org/wiki/Algorithm_Implementation/Strings/Longest_common_substring#Python2
def longest_common_sublist(s1, s2):
    m = [[0] * (1 + len(s2)) for i in xrange(1 + len(s1))]
    longest, x_longest = 0, 0
    for x in xrange(1, 1 + len(s1)):
        for y in xrange(1, 1 + len(s2)):
            if s1[x - 1] == s2[y - 1]:
                m[x][y] = m[x - 1][y - 1] + 1
                if m[x][y] > longest:
                    longest = m[x][y]
                    x_longest = x
            else:
                m[x][y] = 0
    return s1[x_longest - longest: x_longest]

# Loop over the dirs containing the chunks
for path, subdirs, files in os.walk(sys.argv[1]):
    for name in files:
        f = os.path.join(path, name)
        # Skip unwanted files
        if not re.match('^[0-9]', name): continue 
        # Standard sentence ID
        sentence_id = '%02d' % int(os.path.splitext(name)[0])
        if sentence_id not in all_chunks.keys():
            all_chunks[sentence_id] = {}
        # links
        if 'twm-links' in path:
            links = json.load(codecs.open(f, 'rb', 'utf-8'))
            link_chunks = set()
            for sentence, val in links.iteritems():
                all_chunks[sentence_id]['sentence'] = sentence
                for diz in val:
                    # Skip chunks if they are in a stopwords list
                    chunk = diz['chunk']
                    if chunk.lower() in stopwords.StopWords.words('italian'): continue
                    link_chunks.add(chunk)
            all_chunks[sentence_id]['twm-links'] = link_chunks
        # n-grams
        elif 'twm-ngrams' in path:
            ngrams = json.load(codecs.open(f, 'rb', 'utf-8'))
            ngram_chunks = set()
            for val in ngrams.values():
                for diz in val:
                    # Skip chunks if they are in a stopwords list
                    chunk = diz['chunk']
                    if chunk.lower() in stopwords.StopWords.words('italian'): continue
                    ngram_chunks.add(diz['chunk'])
            all_chunks[sentence_id]['twm-ngrams'] = ngram_chunks
        # TextPro
        elif 'textpro-chunks' in path:
            with codecs.open(f, 'rb', 'utf-8') as i:
                tp = [l.strip() for l in i.readlines()]
            tmp_tp_chunks = []
            # Parse TextPro format
            for line in tp:
                if line.startswith('#'): continue
                items = line.split('\t')
                token = items[0]
                tag = items[3]
                if tag == 'B-NP': chunk = [token]
                elif tag == 'I-NP': chunk.append(token)
                else: continue
                tmp_tp_chunks.append(chunk)

            tp_chunks = []
            for chunk in tmp_tp_chunks:
                if chunk not in tp_chunks: tp_chunks.append(chunk)
            tp_chunks = set([' '.join(chunk) for chunk in tp_chunks])
            all_chunks[sentence_id]['textpro-chunks'] = tp_chunks

if debug:
    print all_chunks

all_combined = []

# Combine results
for sentence_id, values in all_chunks.iteritems():
    current = {'id': sentence_id, 'sentence': values['sentence']}
    # If chunks overlap, prefer links > ngrams > chunker
    link_chunks = values['twm-links']
    ngram_chunks = values['twm-ngrams']
    tp_chunks = values['textpro-chunks']
    if debug:
        print 'LINKS'
        print link_chunks
        print 'NGRAMS'
        print ngram_chunks
        print 'TEXTPRO'
        print tp_chunks
    # Prune ngrams from links
    to_remove = set()
    for link_chunk in link_chunks:
        for ngram_chunk in ngram_chunks:
            # Prune whether the link is an ngram substring or viceversa
            if link_chunk in ngram_chunk or ngram_chunk in link_chunk:
                to_remove.add(ngram_chunk)
    ngram_chunks.difference_update(to_remove)

    print 'NGRAMS PRUNED FROM LINKS'
    print ngram_chunks

    # Prune TextPro chunks from links
    to_remove = set()
    for link_chunk in link_chunks:
        for tp_chunk in tp_chunks:
            # Prune whether the link is a TextPro chunk substring or viceversa
            if link_chunk in tp_chunk or tp_chunk in link_chunk:
                to_remove.add(tp_chunk)
    tp_chunks.difference_update(to_remove)

    print 'TEXTPRO PRUNED FROM LINKS'
    print tp_chunks

    # Prune TextPro chunks from ngrams
    to_remove = set()
    for ngram_chunk in ngram_chunks:
        for tp_chunk in tp_chunks:
            # Prune whether the ngram is TextPro chunk substring or viceversa
            if ngram_chunk in tp_chunk or tp_chunk in ngram_chunk:
                to_remove.add(tp_chunk)
    tp_chunks.difference_update(to_remove)

    print 'TEXTPRO PRUNED FROM NGRAMS'
    print tp_chunks

    combined = tp_chunks.union(ngram_chunks, link_chunks)
    pairs = itertools.combinations(combined, 2)

    merged_chunks = set()
    to_remove = set()
    # Merge chunks in case of common words
    for p1, p2 in pairs:
        print p1
        print p2
        split1 = p1.split()
        split2 = p2.split()
        common_words = longest_common_sublist(split1, split2)
        if common_words:
            common_substring = ' '.join(common_words)
            print common_substring
            split1 = p1.split(common_substring)
            split2 = p2.split(common_substring)
            total = split1 + [common_substring] + split2
            print ''.join(total)
            merged_chunks.add(''.join(total))
            to_remove.add(p1)
            to_remove.add(p2)

    combined.difference_update(to_remove)
    combined.update(merged_chunks)

    # Cast to list for json serialization
    current['chunks'] = list(combined)
    all_combined.append(current)
    print 'COMBINED'
    print current

if debug:
    print all_combined

json.dump(all_combined, codecs.open('chunks.json', 'wb', 'utf-8'), ensure_ascii=False, indent=2)
