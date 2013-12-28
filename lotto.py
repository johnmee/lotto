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

(MON, TUE, WED, THU, FRI, SAT, SUN) = range(7)  # same as datetime.weekday()
DAY_COMBINATIONS = ((SAT,), (MON,), (TUE,), (WED,),
                    (SAT, MON), (SAT, TUE), (SAT, WED), (MON, TUE), (TUE, WED), (MON, WED))
DAY_STRINGS = {MON: 'Mon', TUE: 'Tue', WED: 'Wed', THU: 'Thu', FRI: 'Fri',
               SAT: 'Sat', SUN: 'Sun'}


# ------ Classes -------

class Draw(namedtuple('Draw', 'draw_num date numbers lowest highest')):
    """A sequence of integers identified by a date and draw number."""
    pass


class DrawChart(object):
    """A chart containing Draws with formatting information."""
    DRAWN_STR = '•'
    NOT_DRAWN_STR = ''
    TEXT_COLS = 2  # date and filename
    WHITE = '#FFFFFE'
    GOLD = '#FFFF00'
    BLUE = '#66CCFF'
    PINK = '#FF6FCF'
    GREEN = '#66FF66'
    TALLY_COLORS = OrderedDict([[GOLD, 'Gold'], [BLUE, 'Blue'], [PINK, 'Pink'],
                                [GREEN, 'Green']])
    # Each rule tuple contains required cells with the previous cell at
    # position 0, earlier cells at higher indexes.
    # i.e. row -1     -2     -3     -4
    COLOR_RULES = OrderedDict([[(True,  True), GREEN],
                               [(False, False, True), PINK],
                               [(False, True), BLUE],
                               [(True, ), GOLD]])
    HEADER_HEIGHT = 1
    FOOTER_HEIGHT = 1 + len(COLOR_RULES)  # draw percentages + color tallies

    def __init__(self, results, num_range):
        self.results = results
        self.draws = tuple(itertools.chain(*self.results.values()))
        self.lowest, self.highest = num_range
        self.process()

    def process(self):
        """Create chart from draws in self.results."""
        self.header = self.create_header()
        self.body = self.create_matrix()
        self.colors = self.create_color_matrix()
        self.footer = self.create_footer()
        self.width = len(self.body[0])
        self.height = len(self.header) + len(self.body) + len(self.footer)

    def create_header(self):
        """Return the header rows for this chart."""
        return [['Date', 'File'] + list(range(self.lowest, self.highest + 1))]

    def create_matrix(self):
        """Return matrix of processed draw information."""
        matrix = []
        for fn, draws in self.results.items():
            for draw in draws:
                row = [draw.date, fn]
                row.extend([num in draw.numbers for
                            num in range(self.lowest, self.highest + 1)])
                matrix.append(row)

        # Sort by date, then filename within date.
        date_col, file_col = 0, 1
        matrix.sort(key=itemgetter(date_col, file_col))
        return matrix
        
    def create_footer(self):
        """Return footer rows for this chart."""
        return [self.draw_percentages_row()] + self.tallies_footer()

    def draw_percentages_row(self):
        """Return the draw percentages row for this chart."""
        pcts = [self.calc_draw_percentage(n) for
                n in range(self.lowest, self.highest + 1)]
        return list(itertools.chain(['', 'Draw %'], pcts))

    def calc_draw_percentage(self, n):
        """Return the draw percentage for number n."""
        opps = len(self.draws)
        if opps == 0:
            return ''  # number not in play (division by zero)
        times_drawn = sum((draw.numbers.count(n) for draw in self.draws))
        return '{:.4f}%'.format(times_drawn / opps)

    def tallies_footer(self):
        """Return a 2D list of strings containing color counts by column."""
        colors, names = zip(*self.TALLY_COLORS.items())
        tallies = [[''] * len(colors)]  # column major order
        tallies.extend([names])  
        transposed = list(zip(*self.colors))
        for column in itertools.islice(transposed, self.TEXT_COLS, None):
            tallies.append([column.count(color) for color in colors])
        return list(zip(*tallies))

    def create_color_matrix(self):
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
        start_col = self.TEXT_COLS
        max_rule_length = max((len(rule) for rule in self.COLOR_RULES.keys()))
        width = len(self.body[0])
        height = len(self.body)
        transposed = list(zip(*self.body))
        colors = [[self.WHITE for row in range(height)] for
                  col in range(width)]  # column major order
        for row in range(height):
            for col in range(start_col, width):
                if not self.body[row][col]:
                    continue  # cell is empty
                fourth_previous = max(row - max_rule_length, 0)
                previous_cells = transposed[col][fourth_previous:row]
                previous_cells = tuple(reversed(previous_cells))
                colors[col][row] = self.calc_color(previous_cells,
                                                   self.COLOR_RULES)
        colors = list(zip(*colors))
        # add header and footer rows
        colors = [[self.WHITE for col in range(width)] for
                   row in range(self.HEADER_HEIGHT)] + colors
        colors += [[self.WHITE for col in range(width)] for
                   row in range(self.FOOTER_HEIGHT)]
        return colors

    def calc_color(self, previous_cells, rules):
        """Calculate the color for a given cell."""
        for rule, color in rules.items():
            if len(previous_cells) < len(rule):
                continue
            for check_cell, correct_cell in zip(previous_cells, rule):
                if check_cell != correct_cell:
                    break
            else:
                return color  # found a match
        return self.WHITE

    def cell_text(self):
        """Return 2D list of strings representing this chart."""
        cells = []
        for row in self.body:
            row_text = row[:self.TEXT_COLS]
            row_text.extend([self.DRAWN_STR if cell else self.NOT_DRAWN_STR for
                             cell in row[self.TEXT_COLS:]])
            cells.append(row_text)
        return self.header + cells + self.footer
 

class Reader(object):
    """A reader for CSV files containing lottery data."""
    DRAW_NUM_HEADING = 'Format: Draw Number'.lower()
    DATE_HEADING = 'Draw Date (yyyymmdd)'.lower()
    FIRST_NUM_HEADING = 'Winning Number 1'.lower()
    DELIMITERS = (',', ';', '\t')  # expected CSV delimiters
    MAX_DRAWN_NUMBERS = 9  # OzLotto has 7 + 2 supps
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
                dialect = csv.Sniffer().sniff(f.readline(), self.DELIMITERS)
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
        draw_num_col = headings_lower.index(self.DRAW_NUM_HEADING)
        date_col = headings_lower.index(self.DATE_HEADING)
        first_num_col = headings_lower.index(self.FIRST_NUM_HEADING)
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
            last_col = min(self.MAX_DRAWN_NUMBERS + first_num_col, len(row))
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
                  'draw_percentages': 10.0}

    font_weights = {'text_headings': 'bold',
                    'num_headings': 'medium'}

    def __init__(self, chart, dpi):
        self.chart = chart
        self.dpi = dpi  # image resolution in dots per inch

    def format(self, table):
        """Format table for output to image file."""
        self.truncate_filenames(table)
        rotate_footer_text(table, len(self.chart.footer))
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
        # in case the sum of dimensions in self.dims is not 1.0.
        initial_width = calc_table_width(table)

        for (row, col), cell in table.get_celld().items():
            self.resize_cell(cell, row, col)

        # Scale table width back to original value.
        final_width = calc_table_width(table)
        x_scale = initial_width / final_width
        table.scale(x_scale, 1.0)

    def resize_cell(self, cell, row, col):
        """Resize a single cell."""
        if row == self.chart.height - len(self.chart.footer):
            # first row of the footer (draw percentage)
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
        is_footer = row > self.chart.height - self.chart.FOOTER_HEIGHT
        is_text = col < self.chart.TEXT_COLS or is_footer
        is_draw_percentage = (row == self.chart.height - self.chart.FOOTER_HEIGHT and
                              col >= self.chart.TEXT_COLS)
        font_size = None
        weight = None
        if is_heading:
            font_size = self.font_sizes['headings']
            if is_text:
                weight = self.font_weights['text_headings']
            else:
                weight = self.font_weights['num_headings']
        elif is_draw_percentage:
            font_size = self.font_sizes['draw_percentages']
        else:
            if is_text:
                font_size = self.font_sizes['default']
            else:
                font_size = self.font_sizes['bullets']
        return font_size, weight

    def write(self, filename):
        """Write the results to a PNG image file."""
        cell_text = self.chart.cell_text()

        # Create axes that take up the entire area and add a table.
        plt.figure(figsize=(self.dims['row_width'],
                            self.dims['cell_height'] * 5))
        ax = plt.axes([0, 0, 1, 1])
        table = ax.table(cellText=cell_text,
                         cellColours=self.chart.colors,
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


def rotate_footer_text(table, n, start_col=2):
    """Rotate the text in the -nth row of the table clockwise 90 degrees.

    Args:
        table (matplotlib table)

    """
    row_num = sorted({row for (row, _) in table.get_celld().keys()})[-n]
    cells = (cell for (row, col), cell in table.get_celld().items() if
             row == row_num and col >= start_col)
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
        chart = DrawChart(days_results, args.number_range)
        writer = Writer(chart, args.resolution)
        filename = generate_filename(days, last_date(days_results))
        writer.write(filename)


if __name__ == '__main__':
    main()
