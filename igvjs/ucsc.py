import sys
import re
from flask import request, jsonify, Blueprint

err_message = 'UCSC service is enabled but mysql.connector is not installed. ' \
    'Please install mysql-connector (pip install mysql-connector==2.1.4) ' \
    'if you wish to use the UCSC service.'

try:
    import mysql.connector
except ImportError:
    print err_message

ucsc_blueprint = Blueprint('ucsc', __name__, url_prefix='/ucsc')

# ucsc route
@ucsc_blueprint.route('/')
def ucsc():
    if 'mysql.connector' not in sys.modules:
        return err_message

    db = request.args.get('db')
    table = request.args.get('table')
    chrom = request.args.get('chr')
    start = request.args.get('start')
    end = request.args.get('end')

    if not (db and table and chrom and start and end):
        return "Please specify all parameters (db, table, chrom, start, end)."

    ucsc_host = 'genome-mysql.soe.ucsc.edu'
    ucsc_user = 'genome'

    try:
        connection = mysql.connector.connect(host=ucsc_host, user=ucsc_user, database=db)
        cur = connection.cursor()

        results = query_ucsc(cur, table, chrom, start, end)

        cur.close()
        connection.close()

    except mysql.connector.Error, e:
        try:
            return "mysql Error [{}]: {}".format(e.args[0], e.args[1])
        except IndexError:
            return "mysql Error: {}".format(str(e))

    return jsonify(results)



def query_ucsc(cursor, table, chrom, start, end):

    def reg2bins(beg, end):
        bin_list = []
        end -= 1
        bin_list.append(0)
        for k in xrange(1 + (beg >> 26), 2 + (end >> 26)):
            bin_list.append(k)
        for k in xrange(9 + (beg >> 23), 10 + (end >> 23)):
            bin_list.append(k)
        for k in xrange(73 + (beg >> 20), 74 + (end >> 20)):
            bin_list.append(k)
        for k in xrange(585 + (beg >> 17), 586 + (end >> 17)):
            bin_list.append(k)
        for k in xrange(4681 + (beg >> 14), 4682 + (end >> 14)):
            bin_list.append(k)
        return bin_list

    start_label = 'chromStart'
    end_label = 'chromEnd'
    base_query = "SELECT * FROM "+table+" WHERE chrom = %s"
    results = []

    cursor.execute("SELECT * FROM information_schema.COLUMNS " \
        "WHERE TABLE_NAME = %s AND COLUMN_NAME = 'chromStart' LIMIT 1", (table,))

    if not cursor.fetchone():
        start_label= "txStart"
        end_label = "txEnd"

    query = base_query + " AND {} >= %s AND {} <= %s".format(start_label, end_label)

    cursor.execute("SELECT * FROM information_schema.COLUMNS " \
        "WHERE TABLE_NAME = %s AND COLUMN_NAME = 'bin' LIMIT 1", (table,))

    if cursor.fetchone():
        bins = reg2bins(int(start), int(end))
        bin_str = '('+','.join(str(bin) for bin in bins)+')'
        query += " AND bin in "+bin_str

    cursor.execute(query, (chrom, start, end))

    for row in cursor.fetchall():
        row_dict = {}
        for description, value in zip(cursor.description, row):
            name = description[0]
            if name == 'chrom':
                name = 'chr'
            elif name == start_label:
                name = 'start'
            elif name == end_label:
                name = 'end'
            row_dict[name] = str(value)
        results.append(row_dict)

    return results
