from src.reader import *

# number of balls
MAX_NUMBERS = 45


class TextChart(object):
    """
    An ascii rendering of lotto data
    """
    @staticmethod
    def _draw_numbers(data):
        """return numbers as columns with an asterix for drawn balls"""
        ret = ''
        for ball in range(1, MAX_NUMBERS+1):
            if ball in data:
                ret += '| * '
            else:
                ret += '|   '
        return ret + '|'

    @staticmethod
    def _header():
        """return a header showing numbered columns"""
        numbers = '|'.join(['{:>3}'.format(idx) for idx in range(1, MAX_NUMBERS+1)])
        return "{:^10} {:^15} |{}|\n".format("Date", "Game", numbers)

    @staticmethod
    def render(lotto):
        """return a string representation of the lotto data"""
        string = TextChart._header()
        for draw in lotto:
            string += "{} {:^15} {}\n".format(draw.date, draw.label, TextChart._draw_numbers(draw.numbers))
        return string



# load lotto data
draws = LottoCollection()
draws.import_file('OzLotto', OZ_FILENAME)
draws.import_file('TattsLotto', TATTS_FILENAME)
draws.import_file('WeekLotto', WEEK_FILENAME)
draws.sort()
weekdraws = draws.filter(MON, WED)
print(TextChart.render(draws))
