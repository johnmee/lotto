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

# discard any draws older than this
OLDEST_DRAW = datetime.date.today() - datetime.timedelta(weeks=104)


class LottoDraw(object):
    """
    A single lotto draw.

    date: the date of the draw
    numbers: a list of the numbers drawn
    """
    @staticmethod
    def from_csv(fname):
        """Return a list of lotto draws as imported from the named file

        fname: local file name
        * Assumes the first row (header) can be discarded
        * Discards draws older than OLDEST_DRAW
        """
        draws = list()
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
                draws.append(LottoDraw(date_obj, numbers))
        csvfile.close()
        return draws

    def __init__(self, date, numbers):
        """the date of the draw and a list of numbers drawn"""
        self.date = date
        self.numbers = numbers

    def __lt__(self, other):
        """this draw is less than other if the date is earlier"""
        return self.date < other.date

    def __repr__(self):
        return "{} {}".format(self.date, self.numbers)


class TextChart(object):
    """
    An ascii rendering of lotto data
    """
    def __init__(self):
        self.colormap = ColorMap()

    @staticmethod
    def _header():
        """return a header showing numbered columns"""
        numbers = '|'.join(['{:>3}'.format(idx) for idx in range(1, MAX_BALLS+1)])
        return "{:^10} {:^15} |{}|\n".format("Date", "Game", numbers)

    @staticmethod
    def _footer():
        """return a footer showing numbered columns"""
        numbers = '|'.join(['{:>3}'.format(idx) for idx in range(1, MAX_BALLS+1)])
        return "{:^10} {:^15} |{}|\n".format("", "", numbers)

    @staticmethod
    def _label(drawdate):
        """return the name of the lotto done on that day"""
        return ('Monday', 'OzLotto', 'Wednesday', 'Thu', 'Fri', 'TattsLotto', 'Sun')[drawdate.weekday()]

    def render(self, draws):
        """return a string representation of the lotto data"""
        string = TextChart._header()
        for draw in draws:
            label = TextChart._label(draw.date)
            columns = ' | '.join(self.colormap.update(draw))
            string += "{} {:^15} | {} |\n".format(draw.date, label, columns)
        string += TextChart._footer()
        return string


class ColorMap(object):
    """
    Returns colors/marks for each number in a draw
    """
    GREEN, GOLD, BLUE, PINK, DRAWN, BLANK = 'C', 'G', 'B', 'P', '*', ' '

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
            return self.BLANK
        try:
            if self.is_green(ball):
                return self.GREEN
            if self.is_gold(ball):
                return self.GOLD
            if self.is_blue(ball):
                return self.BLUE
            if self.is_pink(ball):
                return self.PINK
        except TypeError:
            pass
        return self.DRAWN

    def update(self, draw):
        """Returns an array of color marks. Pushes draw onto the stack."""
        self._threeback = self._twoback
        self._twoback = self._last
        self._last = self._this
        self._this = draw.numbers

        # a list of colors; one for every ball in the draw
        columns = []
        for ball in range(1, MAX_BALLS+1):
            columns.append(self.get_color(ball))
        return columns


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
    ozlotto = LottoDraw.from_csv(OZ_FILENAME)
    tattslotto = LottoDraw.from_csv(TATTS_FILENAME)
    weeklotto = LottoDraw.from_csv(WEEK_FILENAME)

    # put all the draws together
    draws = ozlotto + tattslotto + weeklotto
    draws.sort()

    # filter for specific days
    mondays = [draw for draw in draws if draw.date.weekday() == 2]
    chart = TextChart()
    print(chart.render(draws))
