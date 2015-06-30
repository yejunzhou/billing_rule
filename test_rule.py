import time
import rule

__author__ = 'brian'

import unittest


class MyTestCase(unittest.TestCase):
    def get_time_range(self, in_time_str, out_time_str):
        in_time = time.mktime(time.strptime(in_time_str, rule.ISOTIMEFORMATS))
        out_time = time.mktime(time.strptime(out_time_str, rule.ISOTIMEFORMATS))
        return in_time, out_time

    def test_temp_one_hour_08_40__09_40(self):
        in_time, out_time = self.get_time_range('2015-05-09 08:40:00', '2015-05-09 09:40:00')
        result = rule.park_charge(rule.CarType.BLUE, in_time, out_time)
        self.assertEqual(result, 0.5)




    def test_temp_one_tmp(self):
        in_time, out_time = self.get_time_range('2015-05-12 19:10:00', '2015-05-12 19:11:00')
        result = rule.park_charge(rule.CarType.BLUE, in_time, out_time)
        self.assertEqual(result, 0.0)

    def test_temp_free_08_00__08_30(self):
        in_time, out_time = self.get_time_range('2015-05-09 08:00:00', '2015-05-09 08:30:00')
        result = rule.park_charge(rule.CarType.BLUE, in_time, out_time)
        self.assertEqual(result, 0.0)

    def test_temp_24_hour(self):
        in_time, out_time = self.get_time_range('2015-05-09 08:00:00', '2015-05-10 08:00:00')
        result = rule.park_charge(rule.CarType.BLUE, in_time, out_time)
        self.assertEqual(result, 15.0)

    def test_temp_over_24_hour(self):
        in_time, out_time = self.get_time_range('2015-05-09 08:00:00', '2015-05-10 08:01:00')
        result = rule.park_charge(rule.CarType.BLUE, in_time, out_time)
        self.assertEqual(result, 15.5)

    def test_temp_add(self):
        in_time, out_time = self.get_time_range('2015-05-09 18:29:00', '2015-05-09 19:01:00')
        result = rule.park_charge(rule.CarType.BLUE, in_time, out_time)
        self.assertEqual(result, 2.5)

    def test_temp_period2_19_00__19_31(self):
        in_time, out_time = self.get_time_range('2015-05-09 19:00:00', '2015-05-09 19:31:00')
        result = rule.park_charge(rule.CarType.BLUE, in_time, out_time)
        self.assertEqual(result, 2)

    def test_temp_period2_19_00__19_31(self):
        in_time, out_time = self.get_time_range('2015-05-09 19:00:00', '2015-05-09 19:31:00')
        result = rule.park_charge(rule.CarType.BLUE, in_time, out_time)
        self.assertEqual(result, 2)

    def test_temp_period2_21_00__21_31(self):
        in_time, out_time = self.get_time_range('2015-05-09 21:00:00', '2015-05-09 21:31:00')
        result = rule.park_charge(rule.CarType.BLUE, in_time, out_time)
        self.assertEqual(result, 5)

    def test_temp_period2_21_00__07_00(self):
        in_time, out_time = self.get_time_range('2015-05-09 21:00:00', '2015-05-10 07:00:00')
        result = rule.park_charge(rule.CarType.BLUE, in_time, out_time)
        self.assertEqual(result, 5)

    def test_day_19_00__19_30(self):
        in_time, out_time = self.get_time_range('2015-05-09 19:00:00', '2015-05-09 19:30:00')
        result = rule.park_charge_daytime(rule.CarType.BLUE, in_time, out_time)
        self.assertEqual(result, 2.0)

    def test_day_20_30__21_30(self):
        in_time, out_time = self.get_time_range('2015-05-09 20:30:00', '2015-05-09 21:30:00')
        result = rule.park_charge_daytime(rule.CarType.BLUE, in_time, out_time)
        self.assertEqual(result, 7.0)

    def test_day_21_30__06_30(self):
        in_time, out_time = self.get_time_range('2015-05-09 21:30:00', '2015-05-10 06:30:00')
        result = rule.park_charge_daytime(rule.CarType.BLUE, in_time, out_time)
        self.assertEqual(result, 5.0)


    def test_night_07_00__10_00(self):
        in_time, out_time = self.get_time_range('2015-05-09 07:00:00', '2015-05-09 10:00:00')

        result = rule.park_charge_night(rule.CarType.BLUE, in_time, out_time)
        self.assertEqual(result, 1.5)

    # def test_park_charge_night_07_09(self):
    #     in_time, out_time = self.get_time_range('2015-05-09 07:40:00', '2015-05-09 08:40:00')
    #     result = rule.park_charge_night(rule.CarType.BLUE, in_time, out_time)
    #     self.assertEqual(result, 2.0)


if __name__ == '__main__':
    unittest.main()
