#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Purpose
-------
This module substitutes positions with a low depth of coverage
in a Multiple Sequence Alignment with 'N'. It ignores gaps at
the start and end of each aligned sequence. The depth of coverage
value below which the process masks positions can be set. By default,
it will not mask gaps/indels contained in the aligned sequences but
the user can change that behaviour.

"""


import os
import re
import csv
import argparse
import datetime as dt

from Bio import SeqIO


def import_depth(tsv_file):
    """Import data from a TSV file.

    Parameters
    ----------
    tsv_file : str
        Path to the TSV file.

    Returns
    -------
    lines : list of list
        List with one sublist per line in
        the TSV file.
    """
    with open(tsv_file, 'r') as tf:
        lines = list(csv.reader(tf, delimiter='\t'))

    return lines


def import_seqs(fasta_file):
    """Import sequences from a FASTA file.

    Parameters
    ----------
    fasta_file : str
        Path to the FASTA file.

    Returns
    -------
    seqs : list of list
        List with one sublist per sequence in the
        FASTA file. Each sublist the identifier/header
        of the sequence (str) and the sequence (str).
    """
    seqs = []
    for record in SeqIO.parse(fasta_file, 'fasta'):
        seqid = record.id
        sequence = str(record.seq)
        seqs.append([seqid, sequence])

    return seqs


def main(input_file, output_file, depth_files, depth_threshold, mask_gaps):

    start_date = dt.datetime.now()
    start_date_str = dt.datetime.strftime(start_date, '%Y-%m-%dT%H:%M:%S')
    print('Started at: {0}\n'.format(start_date_str))

    # import sequences in MSA FASTA file
    msa_seqs = import_seqs(input_file)

    # keep reference and samples separate
    reference = msa_seqs[0]
    reference_id = reference[0]
    samples = msa_seqs[1:]
    sample_ids = [s[0] for s in samples]
    print('Reference:\n{0}'.format(reference_id))
    print('\nAligned samples:\n{0}\nTotal: {1}'.format('\n'.join(sample_ids),
                                                       len(sample_ids)))

    # list depth files and match sample to depth file
    if os.path.isdir(depth_files) is True:
        depth_files = os.listdir(depth_files)
        sample_map = {}
        for i in sample_ids:
            match = [f for f in depth_files if i in f]
            if len(match) > 0:
                file = os.path.join(depth_files, match[0])
                sample_map[i] = file
            else:
                print('Could not find a depth file for '
                      'sample {0}'.format(i))
    # user provided a TSV file with sample to file correspondence
    elif os.path.isfile(depth_files) is True:
        with open(depth_files, 'r') as df:
            lines = csv.reader(df, delimiter='\t')
            sample_map = {l[0]: l[1] for l in lines}

    out_dir = os.path.dirname(output_file)
    pos_basename = os.path.basename(output_file).split('.fasta')[0]
    pos_file = os.path.join(out_dir, pos_basename+'_pos')

    # determine gaps in reference
    # match '-' in reference
    ref_gaps = list(re.finditer('(-)+', reference[1]))
    ref_gaps = [s.span() for s in ref_gaps]
    gaps = {s[0]: s[1]-s[0] for s in ref_gaps}

    for i, sample in enumerate(samples):

        seqid = sample[0]
        sequence = sample[1]

        # determine initial and final subsequences with '-'
        left_trimmed = sequence.lstrip('-')
        left_pos = len(sequence) - len(left_trimmed)
        right_trimmed = sequence.rstrip('-')
        right_pos = len(sequence) - (len(sequence) - len(right_trimmed))

        # import depth data
        depth_info = import_depth(sample_map[seqid])

        # get positions with zero coverage
        zero_cov = [d for d in depth_info if int(d[2]) <= depth_threshold]

        # shift low depth positions based on gaps on reference
        for p in gaps:
            current_p = p
            shift = gaps[p]
            zero_cov = [[z[0], str(int(z[1])+shift), z[2]]
                        if int(z[1])-1 >= current_p
                        else [z[0], z[1], z[2]]
                        for z in zero_cov]

        # after adjusting for gaps on reference we can remove
        # positions on trimmed regions
        zero_cov = [z for z in zero_cov
                    if int(z[1]) > left_pos
                    and int(z[1]) <= right_pos]

        total = len(zero_cov)
        print('\nFound a total of {0} positions with '
              'low depth for sample {1}.\n'.format(total, seqid))

        print('Masking low depth positions in {0}...'.format(seqid))

        splitted = list(sequence)

        masked = 0
        zero_pos = []
        for pos in zero_cov:
            # Python indexing starts at 0
            low_cov_pos = int(pos[1]) - 1
            current = splitted[low_cov_pos]
            if current != '-' or mask_gaps is True:
                splitted[low_cov_pos] = 'N'
                print('{0}: {1} --> N'.format(pos[1], current))
                zero_pos.append(pos[1])
                masked += 1

        print('Masked {0}/{1}'.format(masked, total))

        samples[i][1] = ''.join(splitted)

        # save info about positions below coverage
        with open(pos_file, 'a') as pf:
            pos_info = '{0}\t{1}\t{2}\n'.format(seqid, total,
                                                ','.join(zero_pos))
            pf.write(pos_info)

    # write masked sequences to FASTA
    with open(output_file, 'w') as out:
        reference_record = ['>{0}\n{1}'.format(reference[0], reference[1])]
        samples_records = ['>{0}\n{1}'.format(s[0], s[1]) for s in samples]
        records = reference_record + samples_records
        out_text = '\n'.join(records)
        out.write(out_text)

    end_date = dt.datetime.now()
    end_date_str = dt.datetime.strftime(end_date, '%Y-%m-%dT%H:%M:%S')

    delta = end_date - start_date
    minutes, seconds = divmod(delta.total_seconds(), 60)

    print('\nFinished at: {0}'.format(end_date_str))
    print('Elapsed time: {0:.0f}m{1:.0f}s'.format(minutes, seconds))


def parse_arguments():

    def msg(name=None):

        # simple command with default options
        simple_cmd = ('   python msa_masker.py -i input.fasta '
                      '-df depth_files -o out.fasta')

        # different depth of coverage value
        depth_command = ('  python msa_masker.py -i input.fasta '
                         '-df depth_files -o out.fasta --dc 10')

        # mask gaps contained in sequences
        gaps_command = ('  python msa_masker.py -i input.fasta '
                        '-df depth_files -o out.fasta --dc 10 --mg')

        usage_msg = ('\nSimple command with default options:\n\n{0}\n'
                     '\nDifferent depth of coverage value:\n\n{1}\n'
                     '\nMask gaps in the middle of aligned sequences:'
                     '\n\n{2}\n'.format(simple_cmd,
                                        depth_command,
                                        gaps_command))

        return usage_msg

    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter,
                                     usage=msg())

    parser.add_argument('-i', '--input-file', type=str, required=True,
                        dest='input_file',
                        help='Path to the input FASTA file that contains '
                             'the Multiple Sequence Alignment.')

    parser.add_argument('-o', '--output-file', type=str, required=True,
                        dest='output_file',
                        help='Path to the output FASTA file '
                             'to which the masked sequences '
                             'will be saved.')

    parser.add_argument('-df', '--depth-files', type=str, required=True,
                        dest='depth_files',
                        help='Path to the directory with TSV '
                             'files that contain depth of '
                             'sequencing data. One file per '
                             'sample (files must contain the '
                             'identifier of the sample in the name).')

    parser.add_argument('--dc', '--depth-threshold', type=int, required=False,
                        default=0, dest='depth_threshold',
                        help='Positions with a depth value equal '
                             'or below the value of this argument '
                             'will be substituted by N (default=0).')

    parser.add_argument('--mg', '--mask-gaps', required=False,
                        action='store_true', dest='mask_gaps',
                        help='If the process should mask gaps (-) '
                             'with low depth (default=False).')

    args = parser.parse_args()

    return args


if __name__ == "__main__":

    args = parse_arguments()
    main(**vars(args))
