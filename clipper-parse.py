#!/usr/bin/env python3

from tabula import read_pdf
import pandas as pd
from dateutil.parser import parse
from PyPDF2 import PdfFileReader
import argparse

parser = argparse.ArgumentParser(description = 'Parse Clipper Card history.')
parser.add_argument('clipperpdf', type = str,
                    help = 'PDF of transaction history of Clipper Card')
parser.add_argument('--weekdays', dest = 'weekdays', action = 'store_true')
parser.add_argument('--seven', dest = 'weekdays', action = 'store_false')
parser.set_defaults(weekdays = True)
args = parser.parse_args()

numpages = PdfFileReader(open(args.clipperpdf, "rb")).getNumPages()

for page in range(numpages): # looping because read_pdf output differs per page?!
    clipper_data = read_pdf(args.clipperpdf, silent = True, stream = True, pages = page + 1)

    if 'BALANCE' not in clipper_data.columns:
        # sometimes the parser misses the header
        clipper_data = read_pdf(args.clipperpdf, silent = True, stream = True, pages = page + 1, pandas_options = {'header': None})
        clipper_data.columns = ['TRANSACTION DATE', 'TRANSACTION TYPE', 'LOCATION', 'ROUTE', 'PRODUCT', 'DEBIT', 'CREDIT', 'BALANCE']

    if 'TRANSACTION DATE TRANSACTION TYPE' in clipper_data.columns:
        # sometimes the parser merges these two fields
        groups = clipper_data.iloc[:, 0].apply(lambda x: x.split())
        clipper_data['TRANSACTION DATE'] = groups.apply(lambda x: ' '.join(x[:3]))
        clipper_data['TRANSACTION TYPE'] = groups.apply(lambda x: ' '.join(x[3:]))

    clipper_data = clipper_data.dropna(subset = ['PRODUCT'])
    entrylog = clipper_data.loc[clipper_data['TRANSACTION TYPE'].str.contains("entry")].drop('TRANSACTION TYPE', axis = 1)
    exitlog = clipper_data.loc[clipper_data['TRANSACTION TYPE'].str.contains("exit")].drop('TRANSACTION TYPE', axis = 1)

    translog = pd.concat([entrylog.reset_index(drop = True), exitlog.reset_index(drop=True)], axis=1)
    translog = translog.apply(lambda x: x.str.strip("$").astype(float) if (x.name in {"CREDIT", "DEBIT"}) else x).fillna(0)

    translog = pd.concat([translog['TRANSACTION DATE'].iloc[:, 0].apply(lambda x: parse(x).strftime("%a %b %d %p")),
                          translog[['LOCATION']],
                          translog.groupby(translog.columns, axis = 1).sum()[['DEBIT', 'CREDIT']]],
                         axis = 1)
    translog['TOTAL'] = translog['DEBIT'] - translog['CREDIT']
    translog.drop(['DEBIT', 'CREDIT'], axis = 1, inplace = True)

    if args.weekdays:
        print('\nDropping weekends:\n')
        indexNames = [x.startswith('S') for x in translog['TRANSACTION DATE']]
        translog.drop(translog[indexNames].index, inplace = True)

    print(translog)