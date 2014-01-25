#!/usr/bin/python3

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
TALLY_NAMES = ('Green', 'Gold', 'Blue', 'Pink', 'Drawn', 'Not Drawn')

(MON, TUE, WED, THU, FRI, SAT, SUN) = range(7)  # same as datetime.weekday()
DRAW_COMBINATIONS = (
    (SAT,), (MON,), (TUE,), (WED,),
    (SAT, MON), (SAT, TUE), (SAT, WED), (MON, TUE), (TUE, WED), (MON, WED)
)


class Colors:
    """Enumeration to indicate color of cells on the chart"""
    GREEN = 0
    GOLD = 1
    BLUE = 2
    PINK = 3
    WHITE = 4
    NONE = 5


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
            try:
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
            except IndexError:
                print("IndexError in row: {}".format(row))
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
                return Colors.NONE
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


class HTMLWriter(object):
    """
    an html rendering of chart
    """
    template = """<html>
<head>
    <style>
        table {{ border-collapse: collapse; font-size: 7pt; }}
        tr.bold {{ font-weight: bold; }}
        td {{ white-space: nowrap; border: 1px solid black; width:20px; text-align:center; }}
        .date {{ padding: 2px 5px; }}
    </style>
</head><body>
<h1>{title}</h1><table>\n{table}\n</table>
</body></html>
"""

    def __init__(self, chart, title):
        self.chart = chart
        self.title = "_".join([LOTTO_NAME_MAP[game] for game in title])

    @staticmethod
    def _row_of_numbers():
        html = "<tr class='bold'><td>Date</td><td>Game</td><td>"
        html += "</td><td>".join([str(x) for x in BALLS])
        html += "</td></tr>"
        return html

    def _table_data(self):
        table = ""
        for row in self.chart.rows:
            table += "<tr><td class='date'>{}</td><td class='date'>{}</td>".format(row['date'], row['name'])
            for cell in row['colors']:
                bullet = '&bull;'
                if cell == Colors.NONE:
                    bullet = ''
                bgcolor = ('lightgreen', 'gold', 'lightblue', 'pink', 'white', 'white')[cell]
                table += "<td style='background-color: {}'>{}</td>".format(bgcolor, bullet)
            table += "</tr>\n"
        return table

    def _tallies(self):
        """return a footer showing numbered columns"""
        html = ""
        for tally in TALLY_NAMES:
            row = "<tr><td colspan=2>{}</td><td>".format(tally)
            row += "</td><td>".join([str(x) for x in self.chart.tallies[tally]])
            row += "</td></tr>"
            html += row
        return html

    def save(self, fname):
        table = ""
        table += self._row_of_numbers()
        table += self._table_data()
        table += self._row_of_numbers()
        table += self._tallies()
        html = self.template.format(title=self.title, table=table)
        with open(fname, 'w') as file:
            file.write(html)


if __name__ == '__main__':
    print(datetime.datetime.now())

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

    # load lotto data
    ozlotto = list(LottoDraw.from_csv(OZ_FILENAME))
    tattslotto = list(LottoDraw.from_csv(TATTS_FILENAME))
    weeklotto = list(LottoDraw.from_csv(WEEK_FILENAME))

    # put all the draws together
    all_draws = ozlotto + tattslotto + weeklotto
    all_draws.sort()

    # chart every combo and create an index file
    with open('html/index.html', 'w') as file:
        file.write("<h1>Lapp Lotto</h1>")
        for combo in DRAW_COMBINATIONS:
            draws = [draw for draw in all_draws if draw.date.weekday() in combo]
            chart = LottoChart(draws)
            writer = HTMLWriter(chart, combo)
            writer.save('html/{}.html'.format(writer.title))
            file.write("<p><a href='{0}.html'>{0}</a></p>".format(writer.title))
            print(writer.title)
