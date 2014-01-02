import argparse
import csv
import datetime
import urllib.request

TATTS_URL = "https://tatts.com/LottoHistoricWinningNumbers/"
TATTS_FILENAME = 'Tattslotto.csv'
OZ_FILENAME = 'OzLotto.csv'
WEEK_FILENAME = 'MondayWednesdayLotto.csv'

OLDEST_DRAW = datetime.date.today() - datetime.timedelta(weeks=104)
(MON, TUE, WED, THU, FRI, SAT, SUN) = range(7)  # same as datetime.weekday()


class LottoDraw(object):
    """
    A single lotto draw.

    date: the date of the draw
    numbers: a list of the numbers drawn
    """
    def __init__(self, date, label, numbers):
        self.date = date
        self.label = label
        self.numbers = numbers

    def __lt__(self, other):
        """this draw is less than other if the date is earlier"""
        return self.date < other.date

    def __repr__(self):
        return "{} {} {}".format(self.date, self.label, self.numbers)


class LottoCollection(object):
    """
    A collection of draws for a Lotto game
    """
    def __init__(self):
        self._draws = list()

    def __iter__(self):
        return self._draws.__iter__()

    def __repr__(self):
        return "\n".join([str(draw) for draw in self._draws])

    def sort(self):
        self._draws.sort(key=lambda d: d.date)

    def import_file(self, name, fname):
        """
        import draws from file

        + assumes the first row can be discarded; the header
        """
        with open(fname, 'r', newline='') as csvfile:
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
                    self._draws.append(LottoDraw(date_obj, name, numbers))

    def filter(self, *days):
        """
        Return a lotto object with only draws occuring on the days of the week
        days: integers 0..6 matching days of the week Mon..Sun
        """
        obj = self.__class__()
        obj._draws = [draw for draw in self._draws if draw.date.weekday() in days]
        return obj


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
    draws = LottoCollection()
    draws.import_file('OzLotto', OZ_FILENAME)
    draws.import_file('TattsLotto', TATTS_FILENAME)
    draws.import_file('WeekLotto', WEEK_FILENAME)
    draws.sort()

    # filter for specific days
    weekdraws = draws.filter(MON, WED)
    print(draws)
