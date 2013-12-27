import argparse
from collections import namedtuple, OrderedDict
import csv
import datetime
import itertools
import matplotlib.pyplot as plt
from operator import itemgetter
import os.path
import string
import sys
import logging

# ----- Constants ------

DELIMITERS = (',', ';', '\t')  # expected CSV delimiters
MAX_DRAWN_NUMBERS = 9  # OzLotto has 7 + 2 supps
DRAWN_STR = '•'
NOT_DRAWN_STR = ''
DRAW_NUM_HEADING = 'Format: Draw Number'.lower()
DATE_HEADING = 'Draw Date (yyyymmdd)'.lower()
FIRST_NUM_HEADING = 'Winning Number 1'.lower()
(MON, TUE, WED, THU, FRI, SAT, SUN) = range(7)  # same as datetime.weekday()
DAY_COMBINATIONS = ((SAT,), (MON,), (TUE,), (WED,),
                    (SAT, MON), (SAT, TUE), (SAT, WED), (MON, TUE), (TUE, WED), (MON, WED))
DAY_STRINGS = {MON: 'Mon', TUE: 'Tue', WED: 'Wed', THU: 'Thu', FRI: 'Fri',
               SAT: 'Sat', SUN: 'Sun'}
WHITE = '#FFFFFE'
GOLD = '#FFFF00'
BLUE = '#66CCFF'
PINK = '#FF6FCF'
GREEN = '#66FF66'
# Each rule tuple contains required cells with the previous cell at
# position 0, earlier cells at higher indexes.
# i.e. row -1     -2     -3     -4
COLOR_RULES = OrderedDict([[(True,  True), GREEN],
                           [(False, False, True), PINK],
                           [(False, True), BLUE],
                           [(True, ), GOLD]])


# ------ Classes -------

class Draw(namedtuple('Draw', 'draw_num date numbers lowest highest')):
    """A sequence of integers identified by a date and draw number."""
    pass


class Reader(object):
    """A reader for CSV files containing lottery data."""
    def __init__(self, filenames, use_headings, abort_on_error, num_range):
        self.filenames = filenames
        self.use_headings = use_headings
        self.abort = abort_on_error
        self.num_range = num_range

    def read_files(self):
        """Return a dictionary mapping filenames to lists of Draws."""
        self.validate_filenames()
        results = {fn: self.read_file(fn) for fn in self.filenames}
        results = process_filenames(results)
        results = {fn: draws for fn, draws in results.items() if draws}
        if len(results) < 1:
            print('ERROR: No results found in input files.')
            sys.exit(1)
        return results

    def read_file(self, filename):
        """Read a CSV file of Lotto Draws.

        Returns:
            list of Draws: Every Draw read from the input file.

        """
        try:
            with open(filename, newline='') as f:
                dialect = csv.Sniffer().sniff(f.readline(), DELIMITERS)
                f.seek(0)
                csv_reader = csv.reader(f, dialect)
                headings_row = [h.strip() for h in csv_reader.__next__()]
                if self.use_headings:
                    return self.read_by_headings(csv_reader, headings_row)
                return self.read_by_order(csv_reader)
        except IOError as err:
            print('ERROR: Cannot read from input file {}.'.format(filename))
            print(err)
            if self.abort:
                sys.exit(1)
            return None

    def read_by_headings(self, csv_reader, headings_row):
        """Return a list of Draws read from csv_reader where column types
        are identified by the column's first cell."""
        headings_lower = [h.strip().lower() for h in headings_row]
        draw_num_col = headings_lower.index(DRAW_NUM_HEADING)
        date_col = headings_lower.index(DATE_HEADING)
        first_num_col = headings_lower.index(FIRST_NUM_HEADING)
        return self.read_by_order(csv_reader, draw_num_col, date_col,
                                  first_num_col)

    def read_by_order(self, csv_reader, draw_num_col=0, date_col=1,
                      first_num_col=2):
        """Return a list of Draws read from csv_reader where column types
        are identified by index.

        Reads columns from first_num_col onward as drawn numbers until a
        cell containing anything other than an integer or hyphen is
        found or MAX_DRAWN_NUMBERS numbers have been read.

        Dates are expected to be in the format 'yyyymmdd'.

        """
        lowest, highest = self.num_range
        draws = []
        for row in csv_reader:
            draw_num = int(row[draw_num_col])
            date = date_from_str(row[date_col])
            numbers = []
            last_col = min(MAX_DRAWN_NUMBERS + first_num_col, len(row))
            for cell in row[first_num_col:last_col]:
                if all((ch in string.digits for ch in cell)):
                    numbers.append(int(cell))
                elif cell != '-':  # numbers may be separated by hyphens
                    break
            draws.append(Draw(draw_num, date, numbers, lowest, highest))
        return draws

    def validate_filenames(self):
        """Check that each filename ends with the .csv extension."""
        for fn in self.filenames:
            if len(fn) < 5 or not fn.lower().endswith('.csv'):
                print('ERROR: File {} missing .csv extension.'.format(fn))
                if self.abort:
                    sys.exit(1)
                self.filenames.remove(fn)


class Writer(object):
    """PNG Image writer for analysed lottery data."""
    date_col = 0
    file_col = 1

    # matplotlib table formatting is poorly supported, so the
    # table dimensions were found by trial and error.  These
    # dimensions look best when the draw draws from 45 numbers and
    # start to look unpresentable at around 50 numbers.  The page width
    # was chosen to be close to a multiple of the width of an A4 sheet
    # of paper.
    # Unfortunately, text size cannot be predicted before rendering so
    # filenames that are too long must be truncated.
    dims = {'row_width': 16,  # inches
            'cell_height': 0.28,
            'footer_height': 0.6,
            'num_width': 0.29,
            'date_width': 1.1,
            'file_width': 1.3,
            'max_filename': 23}  # characters

    font_sizes = {'default': 12.0,  # points
                  'headings': 14.0,
                  'bullets': 24.0,
                  'footer': 10.0}

    font_weights = {'text_headings': 'bold',
                    'num_headings': 'medium'}

    def __init__(self, matrix, colors, dpi):
        self.matrix = matrix
        self.colors = colors
        self.dpi = dpi  # image resolution in dots per inch

    def format(self, table):
        """Format table for output to image file."""
        self.truncate_filenames(table)
        rotate_footer_text(table)
        self.resize_table(table)
        self.format_text(table)

    def truncate_filenames(self, table):
        """Truncate filenames that won't fit in the file column."""
        for (_, col), cell in table.get_celld().items():
            if col == self.file_col:
                text = cell.get_text()
                filename = text.get_text()
                shortened = filename[:self.dims['max_filename']]
                text.set_text(shortened)

    def resize_table(self, table):
        """Resize the pyplot cells according to Writer cell
        dimensions."""
        # Store width so we can restore table size after resizing cells,
        # in case the sum of the dimensions in self.dims is not 1.0.
        initial_width = calc_table_width(table)

        for (row, col), cell in table.get_celld().items():
            self.resize_cell(cell, row, col)

        # Scale table width back to original value.
        final_width = calc_table_width(table)
        x_scale = initial_width / final_width
        table.scale(x_scale, 1.0)

    def resize_cell(self, cell, row, col):
        """Resize a single cell."""
        if row == len(self.matrix) - 1:
            cell.set_height(self.dims['footer_height'])
        else:
            cell.set_height(self.dims['cell_height'])
        if col == self.date_col:
            cell.set_width(self.dims['date_width'])
        elif col == self.file_col:
            cell.set_width(self.dims['file_width'])
        else:
            cell.set_width(self.dims['num_width'])

    def format_text(self, table):
        """Set font sizes and weights."""
        table.auto_set_font_size(False)
        for (row, col), cell in table.get_celld().items():
            font_size, weight = self.cell_font_size_weight(row, col)
            text = cell.get_text()
            text.set_fontsize(font_size)
            text.set_weight(weight)

    def cell_font_size_weight(self, row, col):
        """Return the font size and weight for the cell at (row, col)
        according to predetermined constants."""
        is_heading = row == 0
        is_text = col in (self.date_col, self.file_col)
        is_footer = row == len(self.matrix) - 1
        font_size = None
        weight = None
        # TODO: refactor
        if is_heading:
            font_size = self.font_sizes['headings']
            if is_text:
                weight = self.font_weights['text_headings']
            else:
                weight = self.font_weights['num_headings']
        elif is_footer:
            font_size = self.font_sizes['footer']
        else:
            if is_text:
                font_size = self.font_sizes['default']
            else:
                font_size = self.font_sizes['bullets']
        return font_size, weight

    def cell_text(self):
        """Get text for table cells."""
        matrix = self.matrix
        cell_text = []
        for row in matrix[1:-1]:
            l = [row[self.date_col], row[self.file_col]]
            l.extend([DRAWN_STR if n else NOT_DRAWN_STR for n in row[2:]])
            cell_text.append(l)
        cell_text.append(matrix[-1])  # footer containing draw percentages
        headings = matrix[0]  # passed separately to table()
        return headings, cell_text

    def write(self, filename):
        """Write the results to a PNG image file."""
        # Get the column headings and a 2D array of cells.
        headings, cell_text = self.cell_text()

        # Create axes that take up the entire area and add a table.
        plt.figure(figsize=(self.dims['row_width'],
                            self.dims['cell_height'] * 5))
        ax = plt.axes([0, 0, 1, 1])
        table = ax.table(cellText=cell_text,
                cellColours=self.colors[1:],
                         colLabels=headings,
                         cellLoc='center',
                         loc='center')
        self.format(table)
        ax.axis('off')  # hide the axes that come with every plot
        logging.debug('Saving {}...'.format(filename))
        plt.savefig(filename, dpi=self.dpi, bbox_inches='tight')
        plt.close('all')
        logging.debug('done.')


# ----- Functions ------

def process_filenames(results):
    """Process filenames for output.

    1. '/path/to/filename.csv' -> 'filename'
    2. 'OzLotto' (any case) -> 'Oz'
    3. 'Tattslotto' (any case) -> 'Tattslotto'
    4. 'MondayWednesdayLotto' -> 'Monday' and 'Wednesday'

    """
    for old_fn, draws in list(results.items()):
        new_fn = strip_path_ext(old_fn)
        if new_fn.lower() == 'ozlotto':
            new_fn = 'Oz'
        elif new_fn.lower() == 'tattslotto':
            new_fn = 'Tattslotto'
        results[new_fn] = draws
        del results[old_fn]
    return separate_mon_wed(results)


def strip_path_ext(filename):
    """Return a string containing the filename without path or
    extension."""
    return os.path.splitext(os.path.basename(filename))[0]


def separate_mon_wed(results, mon_wed_fn='MondayWednesdayLotto'):
    """Return results with values that were under key mon_wed_fn split
    between the two keys 'Monday' and 'Wednesday' depending on their
    date."""
    draws = results.get(mon_wed_fn, None)
    if not draws:
        return results
    del results[mon_wed_fn]
    results['Monday'] = [d for d in draws if d.date.weekday() == MON]
    results['Wednesday'] = [d for d in draws if d.date.weekday() == WED]
    return results


def date_from_str(s):
    """Return a date object from a string in the format 'yyyymmdd'."""
    year = int(s[:4])
    month = int(s[4:6])
    day = int(s[6:])
    return datetime.date(year, month, day)


def last_date(results):
    """Return the timedate.Date for the latest date in results."""
    draws = tuple(itertools.chain(*results.values()))
    if not draws:
        return None
    return max(draws, key=lambda d: d.date).date


def calc_table_width(table):
    """Return the width of matplotlib table in inches."""
    return sum((cell.get_width() for cell in table.get_celld().values()))


def rotate_footer_text(table):
    """Rotate the text in every cell in the footer by 90 degrees.

    Args:
        table (matplotlib table)

    """
    row_num = max((k[0] for k in table.get_celld().keys()))
    cells = (cell for (row, _), cell in table.get_celld().items() if
             row == row_num)
    for cell in cells:
        text = cell.get_text()
        text.set_rotation(270)


def generate_filename(days, last_date, ext='.png'):
    """Return a unique image filename for these days and date."""
    first_day = SAT  # starting day of the week for sorting
    sorted_days = sorted(days, key=lambda d: (d - first_day) % 7)
    days_str = '_'.join((DAY_STRINGS[day] for day in sorted_days))
    date_str = str(last_date).replace('-', '_')
    filename = '_'.join((date_str, days_str))
    return ''.join((filename, ext))


def filter_by_weekdays(results, days):
    """Return results with only the draws that fall on a day in days."""
    filtered = {fn: [draw for draw in draws if draw.date.weekday() in days] for
                fn, draws in results.items()}
    days_found = set()
    for draws in filtered.values():
        days_found.update({d.date.weekday() for d in draws})
    if len(days_found) < len(days):
        return {}  # these entries will be covered by another days tuple
    return filtered


def filter_by_cutoff_date(results, weeks):
    """Return results with only the draws from after (last draw - weeks)."""
    if results == {}:
        return {}
    cutoff = last_date(results) - datetime.timedelta(weeks=weeks)
    return {fn: [draw for draw in draws if draw.date > cutoff] for
            fn, draws in results.items()}


def filter_results(results, days, weeks):
    """Return results with only the draws within the last "weeks" weeks
    that land on a day in days.

    Returns:
        dict (str: list of Draws): results filtered by days and weeks.

    """
    filtered = filter_by_weekdays(results, days)
    filtered = filter_by_cutoff_date(filtered, weeks)
    return {fn: draws for fn, draws in filtered.items() if draws}


def calc_draw_percentages(results, num_range):
    """Return the draw percentages for numbers in num_range."""
    lowest, highest = num_range
    pcts = {}
    draws = tuple(itertools.chain(*(results[fn] for fn in results)))
    opps = len(draws)
    for n in range(lowest, highest + 1):
        if opps == 0:
            percentage = ''  # number not in play (division by zero)
        else:
            times_drawn = sum((draw.numbers.count(n) for draw in draws))
            percentage = times_drawn / opps
            percentage = '{:.4f}%'.format(percentage)
        pcts[n] = percentage
    return pcts


def calc_color(previous_cells, rules):
    """Calculate the color for a cell preceded by previous_cells.

    Args:
        previous_cells (list of bools): The zero or more cells that
            preceded the cell whose color we're calculating.
        rules (dict {list of bools: string}): A mapping of
            previous cell possibilities to their colors.

    """
    # Note that all rules must be mutually exclusive unless rules is
    # OrderedDict.
    for rule, color in rules.items():
        if len(previous_cells) < len(rule):
            continue
        for check_cell, correct_cell in zip(previous_cells, rule):
            if check_cell != correct_cell:
                break  # does not match this rule
        else:
            return color  # found a match
    return WHITE


def create_color_matrix(matrix, start_row=1, start_col=2, has_footer=True):
    """Create a matrix of colors according to predefined rules.

    Coloring rules:
        Each cell in the area of the matrix defined by start_row,
        start_col, and has_footer is colored depending on the cells in
        the same column in the rows above.

    Returns:
        2D list of strings/None: A 2D list of the same dimensions as
        matrix, where each cell in the area defined by start_row,
        start_col, and has_footer is one of (None, GOLD, BLUE, PINK,
        GREEN).

    """
    end_col = len(matrix[0]) - 1
    end_row = len(matrix) - 1
    if has_footer:
        end_row -= 1
    transposed = list(zip(*matrix))
    colors = [[WHITE for row in range(len(matrix))] for
              col in range(len(matrix[0]))]  # column major order

    for row in range(start_row, end_row + 1):
        for col in range(start_col, end_col + 1):
            if not matrix[row][col]:
                continue  # cell is empty
            fourth_previous = max(row - 4, start_row)
            previous_cells = transposed[col][fourth_previous:row]
            previous_cells = tuple(reversed(previous_cells))
            colors[col][row] = calc_color(previous_cells, COLOR_RULES)
    return list(zip(*colors))


def create_matrix(results, pcts_dict, num_range):
    """Build matrix of draws.

    Args:
        results (dict str: Draw): List of Draws for each filename.
        num_range (2-tuple of ints): Lowest and highest legal numbers.

    """
    # Build the list of draws.
    lowest, highest = num_range
    rows = []
    for fn, draws in results.items():
        for draw in draws:
            row = [draw.date, fn]
            row.extend([num in draw.numbers for
                        num in range(lowest, highest + 1)])
            rows.append(row)

    # Sort by date, then filename within date.
    date_col, file_col = 0, 1
    rows.sort(key=itemgetter(date_col, file_col))

    # Add headings row.
    headings = ['Date', 'File']
    headings.extend(range(lowest, highest + 1))
    rows.insert(0, headings)

    # Add draw percentages footer.
    pcts_list = [pcts_dict[n] for n in range(lowest, highest + 1)]
    rows.append(list(itertools.chain(['', ''], pcts_list)))
    return rows


def parse_args():
    """Parse arguments and perform simple validation."""
    parser = argparse.ArgumentParser()
    parser.description = ('Process and chart lottery data. '
                          'Requires matplotlib.')
    parser.add_argument('inputfiles', nargs='+',
                        help='CSV file(s) to process')
    parser.add_argument('-a', '--abort-on-error', action='store_true',
                        help='exit if an input file cannot be read')
    parser.add_argument('-u', '--use-headings', action='store_true',
                        help='read CSV columns by their headings '
                             'rather than their order')
    parser.add_argument('-n', '--number-range', type=int, nargs=2,
                        default=[1, 45], metavar=('LOW', 'HIGH'),
                        help='the range (inclusive) of numbers that '
                             'may be drawn (default is 1 45)')
    parser.add_argument('-r', '--resolution', type=int, default=120,
                        metavar='DPI',
                        help='output resolution in dots per inch '
                             '(default is 120)')
    parser.add_argument('-v', '--verbose', action='store_true',
                        help='show progress as files are created')
    parser.add_argument('-w', '--weeks', type=int, default=104,
                        help='number of weeks to process from last '
                             'date in inputfiles (default is 104)')

    # swap LOW and HIGH if necessary
    args = parser.parse_args()
    low, high = args.number_range
    if low > high:
        args.number_range.reverse()
    return args


def main():
    args = parse_args()

    # import all the draws from csv
    if args.verbose:
        logging.basicConfig(level=logging.DEBUG)
    logging.debug('Reading input files...')
    reader = Reader(args.inputfiles, args.use_headings,
                    args.abort_on_error, args.number_range)
    draws = reader.read_files()
    logging.debug('done.')

    # generate an image for every combination of days
    for days in DAY_COMBINATIONS:
        days_results = filter_results(draws, days, args.weeks)
        if len(days_results) == 0:
            continue
        draw_pcts = calc_draw_percentages(days_results, args.number_range)
        matrix = create_matrix(days_results, draw_pcts, args.number_range)
        colors = create_color_matrix(matrix)
        writer = Writer(matrix, colors, args.resolution)
        filename = generate_filename(days, last_date(days_results))
        writer.write(filename)


if __name__ == '__main__':
    main()
