import argparse
import csv
import datetime
import urllib.request

# location of the lotto archives
TATTS_URL = "https://tatts.com/LottoHistoricWinningNumbers/"
TATTS_FILENAME = 'Tattslotto.csv'
OZ_FILENAME = 'OzLotto.csv'
WEEK_FILENAME = 'MondayWednesdayLotto.csv'

# number of balls in a draw
MAX_BALLS = 45
BALLS = range(1, MAX_BALLS+1)

# discard any draws older than this
OLDEST_DRAW = datetime.date.today() - datetime.timedelta(weeks=104)

LOTTO_NAME_MAP = ('Monday', 'OzLotto', 'Wednesday', 'Thu', 'Fri', 'TattsLotto', 'Sun')
TALLY_NAMES = ('Green', 'Gold', 'Blue', 'Pink', 'Drawn', 'Blank')


class Colors:
    """Enumeration to indicate color of cells on the chart"""
    GREEN = 0
    GOLD = 1
    BLUE = 2
    PINK = 3
    WHITE = 4
    BLANK = 5


class LottoDraw(object):
    """
    A single lotto draw.

    date: the date of the draw
    numbers: a list of the numbers drawn
    """
    @staticmethod
    def from_csv(fname):
        """Generate lotto draws imported from the named file

        fname: local file name
        * Assumes the first row (header) can be discarded
        * Discards draws older than OLDEST_DRAW
        """
        csvfile = open(fname, 'r', newline='')
        reader = csv.reader(csvfile)
        next(reader)    # discard the first line
        for row in reader:
            # parse the date
            date_string = row[1]
            date_obj = datetime.date(int(date_string[0:4]), int(date_string[4:6]), int(date_string[6:8]))
            if date_obj >= OLDEST_DRAW:
                # collect numbers until not numbers
                numbers = []
                for txt in row[2:]:
                    try:
                        numbers.append(int(txt))
                    except ValueError:
                        # we've run out of numbers
                        break
                # save this draw
                yield LottoDraw(date_obj, numbers)
        csvfile.close()

    def __init__(self, date, numbers):
        """the date of the draw and a list of numbers drawn"""
        self.date = date
        self.numbers = numbers

    def __lt__(self, other):
        """this draw is less than other if the date is earlier"""
        return self.date < other.date

    def __repr__(self):
        return "{} {}".format(self.date, self.numbers)


class LottoChart(object):
    """
    A sequence of lottodraws with metadata
    """
    class ColorMap(object):
        def __init__(self):
            # the current draw and three before
            self._this = self._last = self._twoback = self._threeback = None

        def is_gold(self, ball):
            return ball in self._this and ball in self._last

        def is_green(self, ball):
            return ball in self._this and ball in self._last and ball in self._twoback

        def is_blue(self, ball):
            return ball in self._this and ball not in self._last and ball in self._twoback

        def is_pink(self, ball):
            return ball in self._this and ball not in self._last and \
                   ball not in self._twoback and ball in self._threeback

        def get_color(self, ball):
            """Returns the constant for the mark of this ball in this draw"""
            if ball not in self._this:
                return Colors.BLANK
            try:
                if self.is_green(ball):
                    return Colors.GREEN
                if self.is_gold(ball):
                    return Colors.GOLD
                if self.is_blue(ball):
                    return Colors.BLUE
                if self.is_pink(ball):
                    return Colors.PINK
            except TypeError:
                pass
            return Colors.WHITE

        def update(self, draw):
            """Return a list of colors for every ball in the draw"""

            # push numbers onto the stack
            self._threeback = self._twoback
            self._twoback = self._last
            self._last = self._this
            self._this = draw.numbers

            # a list of colors; one for every ball in the draw
            columns = []
            for ball in BALLS:
                columns.append(self.get_color(ball))
            return columns

    def __init__(self, draws):
        """create a chart from a list of draws"""

        # generate the rows
        self.rows = list()
        colormap = self.ColorMap()
        for draw in draws:
            self.rows.append({
                'date': draw.date,
                'name': LOTTO_NAME_MAP[draw.date.weekday()],
                'colors': colormap.update(draw)
            })

        # tally the frequency of each color of each ball
        self.tallies = {k: [0]*MAX_BALLS for k in TALLY_NAMES}
        for row in self.rows:
            for ball in range(MAX_BALLS):
                color = row['colors'][ball]
                tally = TALLY_NAMES[color]
                self.tallies[tally][ball] += 1


class TextWriter(object):
    """
    An ascii rendering of lotto data
    """
    def __init__(self, chart):
        self.chart = chart

    @staticmethod
    def _header():
        """return a header showing numbered columns"""
        numbers = '|'.join(['{:>3}'.format(idx) for idx in BALLS])
        return "{:^10} {:^15} |{}|\n".format("Date", "Game", numbers)

    def _footer(self):
        """return a footer showing numbered columns"""
        numbers = '|'.join(['{:>3}'.format(idx) for idx in BALLS])
        string = "{:^10} {:^15} |{}|\n\n".format("", "", numbers)
        for mark in TALLY_NAMES:
            tally = self.chart.tallies[mark]
            numbers = '|'.join(['{:>3}'.format(ball) for ball in tally])
            string += "{:10} {:^15} |{}|\n".format('', mark, numbers)
        return string

    def __str__(self):
        """return a string representation of the lotto data"""
        string = TextWriter._header()
        for row in self.chart.rows:
            columns = ' | '.join(map(('C', 'G', 'B', 'P', '*', ' ').__getitem__, row['colors']))
            string += "{} {:^15} | {} |\n".format(row['date'], row['name'], columns)
        string += self._footer()
        return string


# parse commandline arguments
parser = argparse.ArgumentParser('Process and Chart lottery data.')
parser.add_argument('-d', '--download', action='store_true', help='Download the input files from tatts.com')
args = parser.parse_args()

# download lotto archives from the Internet and save to local file
if args.download:
    for filename in (TATTS_FILENAME, OZ_FILENAME, WEEK_FILENAME):
        response = urllib.request.urlopen("{}{}".format(TATTS_URL, filename))
        with open(filename, 'w') as f:
            f.write(response.read().decode('utf-8'))
        print("Downloaded {}".format(filename))


if __name__ == '__main__':
    # load lotto data
    ozlotto = list(LottoDraw.from_csv(OZ_FILENAME))
    tattslotto = list(LottoDraw.from_csv(TATTS_FILENAME))
    weeklotto = list(LottoDraw.from_csv(WEEK_FILENAME))

    # put all the draws together
    draws = ozlotto + tattslotto + weeklotto
    draws.sort()

    # filter for specific days
    mondays = [draw for draw in draws if draw.date.weekday() == 2]
    chart = LottoChart(mondays)
    print(TextWriter(chart))
