#! /usr/bin/env /mnt/nfs/local/python2.5/bin/python
# -*- coding: utf-8 -*-
from bisect import bisect

import os
import sys
import time
import json
import datetime
import string
import binascii
from xml.etree.ElementTree import ElementTree
from models import ecoupon, payrecord, plusconf, cards, schedules, tmprecords
# from mails import fn_timer


ISOTIMEFORMAT = '%Y-%m-%d'
ISOTIMEFORMATS = '%Y-%m-%d %X'
FORMAT_YMDHMS = '%Y-%m-%d %H:%M:%S'
FORMAT_HMS = '%H:%M:%S'


class Section():
    LEFT = 0
    IN = 1
    RIGHT = 2

    def __init__(self):
        pass


class CarType():
    WHITE = 2
    YELLOW = 1
    BLUE = 0

    def __init__(self):
        pass


class CardType():
    TEMPORARY = 0
    MONTHLY = 65
    DAILY = 66
    NIGHTLY = 67


    def __init__(self):
        pass


class ChargeManager(object):
    def __init__(self, car_type, start_timestamp, end_timestamp, card_type=0, ignore_first=0):
        self.car_type = int(car_type)
        self.start_timestamp = start_timestamp
        self.end_timestamp = end_timestamp
        self.card_type = card_type
        self.ignore_first = ignore_first
        self.read_config()


    def read_config(self):
        config = json.loads(open('rule.json', 'rb').read())
        # config = json.read(open('rule.json', 'rb').read())
        self.config_tmp = config['temp']
        self.config_day = config['day']
        self.config_night = config['night']
        if self.card_type == CardType.TEMPORARY:
            self.config_current = config['temp']
        elif self.card_type == CardType.MONTHLY:
            self.config_current = config['temp']
        elif self.card_type == CardType.DAILY:
            self.config_current = config['day']
        elif self.card_type == CardType.NIGHTLY:
            self.config_current = config['night']


    def set_basic(self, config, car_type):
        # pprint(config)
        self.ceiling = config[car_type]['ceiling']
        self.is_army_auto = config['is_army_auto']
        self.is_add = config['is_add']
        self.free_minute = config[car_type]['free_minute']
        self.minute_starts = config[car_type]['minute_starts']
        self.pricing_starts = config[car_type]['pricing_starts']
        self.step = config[car_type]['step']
        self.unit_price = config[car_type]['unit_price']
        self.specified_time = config[car_type]['specified_time']


    def hms2datetime(self, time_hms):
        return datetime.datetime.strptime('2015-01-01 %s' % time_hms, FORMAT_YMDHMS)


    def timestamp2hms(self, timestamp):
        return datetime.datetime.fromtimestamp(int(timestamp)).strftime(FORMAT_HMS)

    def timestamp2datetime(self, timestamp):
        return datetime.datetime.fromtimestamp(int(timestamp))

    def datetime2timestamp(self, dt):
        return time.mktime(dt.timetuple())

    def get_period_range(self, period):
        start_dt, end_dt = self.fix_end_time(self.hms2datetime(period['start_at']),
                                             self.hms2datetime(period['end_at']))

        return [start_dt, end_dt]

    def fix_end_time(self, start_datetime, end_datetime):
        if start_datetime > end_datetime:
            end_datetime += datetime.timedelta(days=1)
        return start_datetime, end_datetime


    def get_period(self, one_datetime):

        period_range = None
        period = None
        # pprint(self.config_current)
        for period in self.specified_time:
            tmp_range = self.get_period_range(period)
            if bisect(self.get_period_range(period), one_datetime) == Section.IN:
                period_range = tmp_range
                break

        return period_range, period


    def get_next_period(self, end_datetime):

        period_range = None
        period = None
        # pprint(self.config_current)
        for period in self.specified_time:
            tmp_range = self.get_period_range(period)
            if bisect(self.get_period_range(period), end_datetime) == Section.IN:
                period_range = tmp_range
                break

        return period_range, period

    def is_across_period(self, current_period_range, period_range):
        print 'is_across_period', current_period_range == period_range, current_period_range, period_range
        if current_period_range == period_range:
            return False
        else:
            return True


    def add_specified(self, current_period, specified):
        hms_range = '%s-%s' % (current_period['start_at'], current_period['end_at'])
        if hms_range in specified:
            specified[hms_range]['total'] += current_period['unit_price']
        else:
            specified[hms_range] = {'total': current_period['unit_price'],
                                    'ceiling': current_period['ceiling']}

    def in_period_charge(self, current_period, current_period_range, specified, start_ts, total):
        if current_period_range is None:  # 时段内收费
            print '基础收费'
            total += self.unit_price
            start_ts += self.step * 60
        else:  # 特殊时段
            print '特殊时段收费'
            self.add_specified(current_period, specified)
            start_ts += current_period['step'] * 60

        return start_ts, total


    def get_next_step(self,period_range,current_period, start_ts):
        if period_range is None:
            next_step=start_ts+self.step*60
        else:
            next_step=start_ts+current_period['step']*60
        return next_step




    def section_charge(self):
        out_charge = 0.0
        if self.car_type == CarType.WHITE:
            if self.config_tmp['is_army_auto']:
                return out_charge
            else:
                self.set_basic(self.config_current, 'blue')
        elif self.car_type == CarType.YELLOW:
            self.set_basic(self.config_current, 'yellow')
        else:
            self.set_basic(self.config_current, 'blue')

        if self.is_free():
            return out_charge

        total = 0.0
        days = (self.end_timestamp - self.start_timestamp) // (24 * 60 * 60)
        start_datetime = self.hms2datetime(self.timestamp2hms(self.start_timestamp))
        end_datetime = self.hms2datetime(self.timestamp2hms(self.end_timestamp))

        print start_datetime, end_datetime
        start_dt, end_dt = self.fix_end_time(start_datetime, end_datetime)
        print type(start_dt), end_dt
        start_ts = self.datetime2timestamp(start_dt)
        end_ts = self.datetime2timestamp(end_dt)

        period_range, period = self.get_period(start_datetime)

        next_step = None

        if period_range is None:
            print '非特殊时段进入'
            if self.ignore_first == 0:
                total += self.pricing_starts
                start_ts += self.minute_starts * 60

            current_period_range = None
            current_period = None
            print '起步价', total
        else:
            print '特殊时段进入'
            current_period_range = period_range
            current_period = period
        print '起步完成',total
        basic_charge = 0.0
        specified = {}
        while start_ts < end_ts:
            print '计算处起步价以外的费用'

            next_step = self.get_next_step(period_range, current_period, start_ts)

            period_range, period_next = self.get_period(self.timestamp2datetime(next_step))
            print start_datetime, period_range
            if self.is_across_period(current_period_range, period_range):
                print '跨时段'
                if self.is_add:  # 叠加收费
                    print '叠加收费>>>>>'
                    if current_period_range is None:  # 基础时段 转 特殊时段
                        total += self.unit_price
                        start_ts = self.datetime2timestamp(period_range[0])
                    else:  # 特殊时段 转 基础时段
                        self.add_specified(current_period, specified)
                        start_ts = self.datetime2timestamp(current_period_range[1])
                else:  # 延续收费 类似于时段内收费
                    print '延续收费>>>>>'
                    start_ts, total = self.in_period_charge(current_period, current_period_range, specified, start_ts, total)
                current_period_range, current_period = period_range, period_next
            else:  # 时段内收费
                start_ts, total = self.in_period_charge(current_period, current_period_range, specified, start_ts, total)
                print '时段内收费', total
            print '>>>>>',total,specified,self.timestamp2datetime(start_ts),self.timestamp2datetime(next_step)

        charge = 0.0
        for key, value in specified.iteritems():
            if 0 <= value['ceiling'] < value['total']:
                charge += value['ceiling']
            else:
                charge += value['total']

        total += charge
        if total > self.ceiling:
            out_charge = self.ceiling * (days + 1)
        else:
            out_charge = self.ceiling * days + total
        return round(out_charge, 1)


    def is_free(self):
        return ((self.end_timestamp - self.start_timestamp) / 60) <= self.free_minute


def park_charge(plate_color, start_time, end_time, ignore_first=0):
    cm = ChargeManager(plate_color, start_time, end_time, CardType.TEMPORARY, ignore_first)
    return cm.section_charge()


def park_charge_daytime(plate_color, start_time, end_time, ignore_first=0):
    cm = ChargeManager(plate_color, start_time, end_time, CardType.DAILY, ignore_first)
    return cm.section_charge()


def park_charge_night(plate_color, start_time, end_time, ignore_first=0):
    cm = ChargeManager(plate_color, start_time, end_time, CardType.NIGHTLY, ignore_first)
    return cm.section_charge()


def ParkCharge(plate_color, start_time, end_time, card_type=0, ignore_first=0):
    if card_type == CardType.TEMPORARY or card_type == CardType.MONTHLY:
        cm = ChargeManager(plate_color, start_time, end_time, CardType.TEMPORARY, ignore_first)
    elif card_type == CardType.DAILY:
        cm = ChargeManager(plate_color, start_time, end_time, CardType.DAILY, ignore_first)
    elif card_type == CardType.NIGHTLY:
        cm = ChargeManager(plate_color, start_time, end_time, CardType.NIGHTLY, ignore_first)
    else:
        cm = ChargeManager(plate_color, start_time, end_time, CardType.TEMPORARY, ignore_first)
    return cm.section_charge()


# def ParkCharge(plate_color,start_time,end_time,card_type=0,ignore_first=0):
#     if card_type == 0 or card_type == 65:
#         return charge_calc(plate_color,start_time,end_time,ignore_first)
#     elif card_type == 66:
#         return charge_calc_66(plate_color,start_time,end_time,ignore_first)
#     elif card_type == 67:
#         return charge_calc_67(plate_color,start_time,end_time,ignore_first)
#
def charge_calc(plate_color, start_time, end_time, ignore_first):
    print '### charge_calc ###'
    rule_path = '/opt/local/wacs/rules/rule.xml'
    tree = ElementTree()
    tree.parse(rule_path)
    ps = tree.find('rules_army')
    rule_set = ps.getiterator('string')
    plate_army_auto = int(rule_set[0].text)
    ps = tree.find('rules_other')
    rule_set = ps.getiterator('string')
    cross_add_up = int(rule_set[0].text)

    out_charge = 0.0
    if int(plate_color) == 2:  # white
        if plate_army_auto != 0:
            return out_charge
        else:
            ps = tree.find('rules_blue')
    elif int(plate_color) == 1:  # yellow
        ps = tree.find('rules_yellow')
    else:
        ps = tree.find('rules_blue')
    rule_set = ps.getiterator('string')

    free_min = int(rule_set[0].text)
    stay_min = (end_time - start_time) / 60
    print "start_time", time.strftime(ISOTIMEFORMATS, time.localtime(start_time)), "end_time", time.strftime(ISOTIMEFORMATS, time.localtime(end_time))
    print "stay_min", stay_min, "free_min", free_min

    if stay_min > free_min:
        if ignore_first != 0:
            first_min = 0
            first_cost = 0
        else:
            first_min = int(rule_set[1].text)
            first_cost = float(rule_set[2].text)

        after_min = int(rule_set[3].text)
        after_cost = float(rule_set[4].text)
        night_min = int(rule_set[5].text)
        night_cost = float(rule_set[6].text)
        night_begin = str(rule_set[7].text)
        night_stop = str(rule_set[8].text)
        max_night = float(rule_set[9].text)
        max_day = float(rule_set[10].text)

        if after_min == 0 or night_min == 0:
            return round(out_charge, 1)

        tmp_str = '2015-01-01 ' + time.strftime('%H:%M:%S', time.localtime(start_time))
        tmp_start_time = time.mktime(time.strptime(tmp_str, ISOTIMEFORMATS))
        if time.strftime('%H:%M:%S', time.localtime(end_time)) >= time.strftime('%H:%M:%S', time.localtime(start_time)):
            tmp_str = '2015-01-01 ' + time.strftime('%H:%M:%S', time.localtime(end_time))
        else:
            tmp_str = '2015-01-02 ' + time.strftime('%H:%M:%S', time.localtime(end_time))
        tmp_end_time = time.mktime(time.strptime(tmp_str, ISOTIMEFORMATS))

        stay_days = (end_time - start_time) // (24 * 60 * 60)
        # first cost
        first_effect = False
        first_charge = first_cost
        daytime_charge = 0
        night_charge = 0

        if time.strftime('%H:%M:%S', time.localtime(tmp_start_time)) < night_begin and \
                        time.strftime('%H:%M:%S', time.localtime(tmp_start_time)) > night_stop:
            if cross_add_up == 1:
                current_time = 'daytime'
        else:  # night
            if cross_add_up == 1:
                current_time = 'night'

        while tmp_start_time < tmp_end_time:
            #print "tmp_start_time",time.strftime(ISOTIMEFORMATS,time.localtime(tmp_start_time))
            if time.strftime('%H:%M:%S', time.localtime(tmp_start_time)) <= night_begin and \
                            time.strftime('%H:%M:%S', time.localtime(tmp_start_time)) >= night_stop:
                if cross_add_up == 1:  #2015-05-11
                    if current_time == 'night':
                        tmp_start_time = time.mktime(time.strptime(time.strftime("%Y-%m-%d ", time.localtime(tmp_start_time)) + night_stop, ISOTIMEFORMATS)) + 1
                        current_time = 'daytime'
                        first_effect = True
                        tmp_start_time += first_min * 60
                    else:
                        if not first_effect:
                            first_effect = True
                            tmp_start_time += first_min * 60
                        else:
                            daytime_charge += after_cost
                            tmp_start_time += after_min * 60

                    if time.strftime('%H:%M:%S', time.localtime(tmp_start_time)) >= night_begin or \
                                    time.strftime('%H:%M:%S', time.localtime(tmp_start_time)) <= night_stop:
                        tmp_start_time = time.mktime(time.strptime(time.strftime("%Y-%m-%d ", time.localtime(tmp_start_time)) + night_begin, ISOTIMEFORMATS)) + 1
                        current_time = 'night'
                    else:
                        current_time = 'daytime'
                else:
                    if not first_effect:
                        first_effect = True
                        tmp_start_time += first_min * 60
                    else:
                        daytime_charge += after_cost
                        tmp_start_time += after_min * 60
            else:  # night
                if cross_add_up == 1:
                    if current_time == 'daytime':

                        tmp_start_time = time.mktime(time.strptime(time.strftime("%Y-%m-%d ", time.localtime(tmp_start_time)) + night_begin, ISOTIMEFORMATS)) + 1
                        current_time = 'night'
                    else:
                        night_charge += night_cost
                        tmp_start_time += night_min * 60
                        if time.strftime('%H:%M:%S', time.localtime(tmp_start_time)) < night_begin and \
                                        time.strftime('%H:%M:%S', time.localtime(tmp_start_time)) > night_stop:
                            tmp_start_time = time.mktime(time.strptime(time.strftime("%Y-%m-%d ", time.localtime(tmp_start_time)) + night_stop, ISOTIMEFORMATS)) + 1
                            current_time = 'daytime'
                            if not first_effect:
                                first_effect = True
                                tmp_start_time += first_min * 60
                        else:
                            current_time = 'night'
                else:
                    night_charge += night_cost
                    tmp_start_time += night_min * 60
                    #print 'daytime_charge',daytime_charge,'night_charge',night_charge

        if night_charge > max_night:
            night_charge = max_night

        if first_effect:
            daytime_charge += first_charge
        #print 'first_effect',first_effect,'first_charge',first_charge,'daytime_charge',daytime_charge
        if night_charge + daytime_charge > max_day:
            out_charge = max_day * (stay_days + 1)
        else:
            out_charge = max_day * stay_days + daytime_charge + night_charge
        print 'stay_days', stay_days, '  out_charge', out_charge
    return round(out_charge, 1)


def charge_calc_66(plate_color, start_time, end_time, ignore_first):
    print '###charge_calc_66 start %s,end %s,' % (start_time, end_time)
    rule_path = '/opt/local/wacs/rules/rule_night.xml'
    tree = ElementTree()
    tree.parse(rule_path)
    ps = tree.find('rules_army')
    rule_set = ps.getiterator('string')
    plate_army_auto = int(rule_set[0].text)
    ps = tree.find('rules_other')
    rule_set = ps.getiterator('string')
    cross_add_up = int(rule_set[0].text)

    out_charge = 0.0
    if int(plate_color) == 2:  # white
        if plate_army_auto != 0:
            return out_charge
        else:
            ps = tree.find('rules_blue')
    elif int(plate_color) == 1:  # yellow
        ps = tree.find('rules_yellow')
    else:
        ps = tree.find('rules_blue')
    rule_set = ps.getiterator('string')

    free_min = int(rule_set[0].text)
    stay_min = (end_time - start_time) / 60
    print "start_time", time.strftime(ISOTIMEFORMATS, time.localtime(start_time)), "end_time", time.strftime(ISOTIMEFORMATS, time.localtime(end_time))
    print "stay_min", stay_min, "free_min", free_min

    if stay_min > free_min:
        if ignore_first != 0:
            first_min = 0
            first_cost = 0
        else:
            first_min = int(rule_set[1].text)
            first_cost = float(rule_set[2].text)

        after_min = int(rule_set[3].text)
        after_cost = float(rule_set[4].text)
        night_min = int(rule_set[5].text)
        night_cost = float(rule_set[6].text)
        night_begin = str(rule_set[7].text)
        night_stop = str(rule_set[8].text)
        max_night = float(rule_set[9].text)
        max_day = float(rule_set[10].text)

        tmp_str = '2015-01-01 ' + time.strftime('%H:%M:%S', time.localtime(start_time))
        tmp_start_time = time.mktime(time.strptime(tmp_str, ISOTIMEFORMATS))
        if time.strftime('%H:%M:%S', time.localtime(end_time)) >= time.strftime('%H:%M:%S', time.localtime(start_time)):
            tmp_str = '2015-01-01 ' + time.strftime('%H:%M:%S', time.localtime(end_time))
        else:
            tmp_str = '2015-01-02 ' + time.strftime('%H:%M:%S', time.localtime(end_time))
        tmp_end_time = time.mktime(time.strptime(tmp_str, ISOTIMEFORMATS))

        stay_days = (end_time - start_time) // (24 * 60 * 60)
        # first cost
        first_effect = False
        first_charge = first_cost
        daytime_charge = 0
        night_charge = 0

        if time.strftime('%H:%M:%S', time.localtime(tmp_start_time)) < night_begin and \
                        time.strftime('%H:%M:%S', time.localtime(tmp_start_time)) > night_stop:
            if cross_add_up == 1:
                current_time = 'daytime'
        else:  # night
            if cross_add_up == 1:
                current_time = 'night'

        while tmp_start_time < tmp_end_time:
            #print "tmp_start_time",time.strftime(ISOTIMEFORMATS,time.localtime(tmp_start_time))
            if time.strftime('%H:%M:%S', time.localtime(tmp_start_time)) <= night_begin and \
                            time.strftime('%H:%M:%S', time.localtime(tmp_start_time)) >= night_stop:
                if cross_add_up == 1:  #2015-05-11
                    if current_time == 'night':
                        tmp_start_time = time.mktime(time.strptime(time.strftime("%Y-%m-%d ", time.localtime(tmp_start_time)) + night_stop, ISOTIMEFORMATS)) + 1
                        current_time = 'daytime'
                        first_effect = True
                        tmp_start_time += first_min * 60
                    else:
                        if not first_effect:
                            first_effect = True
                            tmp_start_time += first_min * 60
                        else:
                            daytime_charge += after_cost
                            tmp_start_time += after_min * 60

                            if time.strftime('%H:%M:%S', time.localtime(tmp_start_time)) >= night_begin or \
                                            time.strftime('%H:%M:%S', time.localtime(tmp_start_time)) <= night_stop:
                                tmp_start_time = time.mktime(time.strptime(time.strftime("%Y-%m-%d ", time.localtime(tmp_start_time)) + night_begin, ISOTIMEFORMATS)) + 1
                                current_time = 'night'
                            else:
                                current_time = 'daytime'
                else:
                    if not first_effect:
                        first_effect = True
                        tmp_start_time += first_min * 60
                    else:
                        daytime_charge += after_cost
                        tmp_start_time += after_min * 60
            else:  # night
                if cross_add_up == 1:
                    if current_time == 'daytime':

                        tmp_start_time = time.mktime(time.strptime(time.strftime("%Y-%m-%d ", time.localtime(tmp_start_time)) + night_begin, ISOTIMEFORMATS)) + 1
                        current_time = 'night'
                    else:
                        night_charge += night_cost
                        tmp_start_time += night_min * 60
                        if time.strftime('%H:%M:%S', time.localtime(tmp_start_time)) < night_begin and \
                                        time.strftime('%H:%M:%S', time.localtime(tmp_start_time)) > night_stop:
                            tmp_start_time = time.mktime(time.strptime(time.strftime("%Y-%m-%d ", time.localtime(tmp_start_time)) + night_stop, ISOTIMEFORMATS)) + 1
                            current_time = 'daytime'
                            if not first_effect:
                                first_effect = True
                                tmp_start_time += first_min * 60
                        else:
                            current_time = 'night'
                else:
                    night_charge += night_cost
                    tmp_start_time += night_min * 60

        if night_charge > max_night:
            night_charge = max_night
        if first_effect:
            daytime_charge += first_charge
        #print 'first_effect',first_effect,'first_charge',first_charge,'daytime_charge',daytime_charge
        if night_charge + daytime_charge > max_day:
            out_charge = max_day * (stay_days + 1)
        else:
            out_charge = max_day * stay_days + daytime_charge + night_charge
        print 'stay_days', stay_days, '  out_charge', out_charge
    return round(out_charge, 1)


def charge_calc_67(plate_color, start_time, end_time, ignore_first):
    print '###charge_calc_67 start %s,end %s,' % (start_time, end_time)
    rule_path = '/opt/local/wacs/rules/rule_daytime.xml'
    tree = ElementTree()
    tree.parse(rule_path)
    ps = tree.find('rules_army')
    rule_set = ps.getiterator('string')
    plate_army_auto = int(rule_set[0].text)
    ps = tree.find('rules_other')
    rule_set = ps.getiterator('string')
    cross_add_up = int(rule_set[0].text)

    out_charge = 0.0
    if int(plate_color) == 2:  # white
        if plate_army_auto != 0:
            return out_charge
        else:
            ps = tree.find('rules_blue')
    elif int(plate_color) == 1:  # yellow
        ps = tree.find('rules_yellow')
    else:
        ps = tree.find('rules_blue')
    rule_set = ps.getiterator('string')

    free_min = int(rule_set[0].text)
    stay_min = (end_time - start_time) / 60
    print "start_time", time.strftime(ISOTIMEFORMATS, time.localtime(start_time)), "end_time", time.strftime(ISOTIMEFORMATS, time.localtime(end_time))
    print "stay_min", stay_min, "free_min", free_min

    if stay_min > free_min:
        if ignore_first != 0:
            first_min = 0
            first_cost = 0
        else:
            first_min = int(rule_set[1].text)
            first_cost = float(rule_set[2].text)

        after_min = int(rule_set[3].text)
        after_cost = float(rule_set[4].text)
        night_min = int(rule_set[5].text)
        night_cost = float(rule_set[6].text)
        night_begin = str(rule_set[7].text)
        night_stop = str(rule_set[8].text)
        max_night = float(rule_set[9].text)
        max_day = float(rule_set[10].text)

        tmp_str = '2015-01-01 ' + time.strftime('%H:%M:%S', time.localtime(start_time))
        tmp_start_time = time.mktime(time.strptime(tmp_str, ISOTIMEFORMATS))
        if time.strftime('%H:%M:%S', time.localtime(end_time)) >= time.strftime('%H:%M:%S', time.localtime(start_time)):
            tmp_str = '2015-01-01 ' + time.strftime('%H:%M:%S', time.localtime(end_time))
        else:
            tmp_str = '2015-01-02 ' + time.strftime('%H:%M:%S', time.localtime(end_time))
        tmp_end_time = time.mktime(time.strptime(tmp_str, ISOTIMEFORMATS))

        stay_days = (end_time - start_time) // (24 * 60 * 60)
        # first cost
        first_effect = False
        first_charge = first_cost
        daytime_charge = 0
        night_charge = 0

        if time.strftime('%H:%M:%S', time.localtime(tmp_start_time)) < night_begin and \
                        time.strftime('%H:%M:%S', time.localtime(tmp_start_time)) > night_stop:
            if cross_add_up == 1:
                current_time = 'daytime'
        else:  # night
            if cross_add_up == 1:
                current_time = 'night'

        while tmp_start_time < tmp_end_time:
            #print "tmp_start_time",time.strftime(ISOTIMEFORMATS,time.localtime(tmp_start_time))
            if time.strftime('%H:%M:%S', time.localtime(tmp_start_time)) <= night_begin and \
                            time.strftime('%H:%M:%S', time.localtime(tmp_start_time)) >= night_stop:
                if cross_add_up == 1:  #2015-05-11
                    if current_time == 'night':
                        tmp_start_time = time.mktime(time.strptime(time.strftime("%Y-%m-%d ", time.localtime(tmp_start_time)) + night_stop, ISOTIMEFORMATS)) + 1
                        current_time = 'daytime'
                        first_effect = True
                        tmp_start_time += first_min * 60
                    else:
                        if not first_effect:
                            first_effect = True
                            tmp_start_time += first_min * 60
                        else:
                            daytime_charge += after_cost
                            tmp_start_time += after_min * 60

                        if time.strftime('%H:%M:%S', time.localtime(tmp_start_time)) >= night_begin or \
                                        time.strftime('%H:%M:%S', time.localtime(tmp_start_time)) <= night_stop:
                            tmp_start_time = time.mktime(time.strptime(time.strftime("%Y-%m-%d ", time.localtime(tmp_start_time)) + night_begin, ISOTIMEFORMATS)) + 1
                            current_time = 'night'
                        else:
                            current_time = 'daytime'
                else:
                    if not first_effect:
                        first_effect = True
                        tmp_start_time += first_min * 60
                    else:
                        daytime_charge += after_cost
                        tmp_start_time += after_min * 60
            else:  # night
                if cross_add_up == 1:
                    if current_time == 'daytime':

                        tmp_start_time = time.mktime(time.strptime(time.strftime("%Y-%m-%d ", time.localtime(tmp_start_time)) + night_begin, ISOTIMEFORMATS)) + 1
                        current_time = 'night'
                    else:
                        night_charge += night_cost
                        tmp_start_time += night_min * 60
                        if time.strftime('%H:%M:%S', time.localtime(tmp_start_time)) < night_begin and \
                                        time.strftime('%H:%M:%S', time.localtime(tmp_start_time)) > night_stop:
                            tmp_start_time = time.mktime(time.strptime(time.strftime("%Y-%m-%d ", time.localtime(tmp_start_time)) + night_stop, ISOTIMEFORMATS)) + 1
                            current_time = 'daytime'
                            if not first_effect:
                                first_effect = True
                                tmp_start_time += first_min * 60
                        else:
                            current_time = 'night'
                else:
                    night_charge += night_cost
                    tmp_start_time += night_min * 60

        if night_charge > max_night:
            night_charge = max_night
        if first_effect:
            daytime_charge += first_charge
        #print 'first_effect',first_effect,'first_charge',first_charge,'daytime_charge',daytime_charge
        if night_charge + daytime_charge > max_day:
            out_charge = max_day * (stay_days + 1)
        else:
            out_charge = max_day * stay_days + daytime_charge + night_charge
        print 'stay_days', stay_days, '  out_charge', out_charge
    return round(out_charge, 1)


def classify_ecoupon(s_time_stamp, elem):
    ecoupon_in_time = {}
    ecoupon_out_time = {}
    ecoupon_ahead_time = {}
    ecoupon_in_time_num = 0
    start_stamp = time.mktime(time.strptime(elem.start_time.strftime(ISOTIMEFORMATS), ISOTIMEFORMATS))
    end_stamp = time.mktime(time.strptime(elem.end_time.strftime(ISOTIMEFORMATS), ISOTIMEFORMATS))
    if s_time_stamp < start_stamp:
        ecoupon_ahead_time = elem
    elif start_stamp < s_time_stamp < end_stamp:
        ecoupon_in_time = elem
        ecoupon_in_time_num += elem.value
    else:
        ecoupon_out_time = elem

    return {'ecoupon_in_time': ecoupon_in_time, 'ecoupon_out_time': ecoupon_out_time,
            'ecoupon_ahead_time': ecoupon_ahead_time, 'ecoupon_in_time_num': ecoupon_in_time_num}


def get_ecoupon(data):
    coupon_times = []
    coupon_times_num = 0
    coupon_hours = []
    coupon_hours_num = 0
    coupon_money = []
    coupon_money_num = 0
    s_time = time.strftime(ISOTIMEFORMATS, time.localtime())
    s_time_stamp = time.mktime(time.strptime(s_time, ISOTIMEFORMATS))
    ecoupon_out_time = []
    ecoupon_ahead_time = []
    ret_times = {'ecoupon_in_time': [], 'ecoupon_in_time_num': 0, 'ecoupon_ahead_time': [], 'ecoupon_out_time': []}
    ret_hours = {'ecoupon_in_time': [], 'ecoupon_in_time_num': 0, 'ecoupon_ahead_time': [], 'ecoupon_out_time': []}
    ret_money = {'ecoupon_in_time': [], 'ecoupon_in_time_num': 0, 'ecoupon_ahead_time': [], 'ecoupon_out_time': []}

    for elem in data:
        if elem.etype == 66:
            ret_times_tmp = classify_ecoupon(s_time_stamp, elem)
            ret_times['ecoupon_in_time'].append(ret_times_tmp['ecoupon_in_time'])
            ret_times['ecoupon_in_time_num'] += ret_times_tmp['ecoupon_in_time_num']
            ret_times['ecoupon_out_time'].append(ret_times_tmp['ecoupon_out_time'])
            ret_times['ecoupon_ahead_time'].append(ret_times_tmp['ecoupon_ahead_time'])
        elif elem.etype == 67:
            ret_hours_tmp = classify_ecoupon(s_time_stamp, elem)
            ret_hours['ecoupon_in_time'].append(ret_hours_tmp['ecoupon_in_time'])
            ret_hours['ecoupon_in_time_num'] += ret_hours_tmp['ecoupon_in_time_num']
            ret_hours['ecoupon_out_time'].append(ret_hours_tmp['ecoupon_out_time'])
            ret_hours['ecoupon_ahead_time'].append(ret_hours_tmp['ecoupon_ahead_time'])
        elif elem.etype == 69:
            ret_money = classify_ecoupon(s_time_stamp, elem)

    coupon_dict_times = dict(msg=ret_times['ecoupon_in_time'], tol=ret_times['ecoupon_in_time_num'],
                             ahead_time=ret_times['ecoupon_ahead_time'], out_time=ret_times['ecoupon_out_time'])
    coupon_dict_hours = dict(msg=ret_hours['ecoupon_in_time'], tol=ret_hours['ecoupon_in_time_num'],
                             ahead_time=ret_hours['ecoupon_ahead_time'], out_time=ret_hours['ecoupon_out_time'])
    coupon_dict_money = dict(msg=ret_money['ecoupon_in_time'], tol=ret_money['ecoupon_in_time_num'],
                             ahead_time=ret_money['ecoupon_ahead_time'], out_time=ret_money['ecoupon_out_time'])

    ret = dict(times=coupon_dict_times, hours=coupon_dict_hours, money=coupon_dict_money)
    print ret
    return ret


def storage_to_dict(storage_obj):
    def datetimeformat(obj):
        if isinstance(obj, datetime.datetime):
            return obj.strftime(ISOTIMEFORMATS)
        else:
            return obj

    return dict((elem[0], datetimeformat(elem[1])) for elem in storage_obj.items())


def EcouponEntry(func):
    def wrapper(args, *arg, **kw):
        print '*' * 50
        print args, arg, kw
        print '*' * 50
        print args['ecoupon_data']
        print '*' * 50
        coupon_hours = 0
        coupon_times = 0
        coupon_money = 0
        ret = {'used_rights': {}}
        if kw['msg']['used_rights'].has_key('VIP'):
            ret['used_rights']['VIP'] = kw['msg']['used_rights']['VIP']

        ret['park_charge'] = args['charge']
        if args['ecoupon_data']:
            used_coupon = list(payrecord.get_coupon(args['record_id']))
            plusconfrow = list(plusconf.get())
            coupon_rule_car = plusconfrow[0].coupon_per_car
            coupon_rule_time = plusconfrow[0].coupon_per_time
            print coupon_rule_car, coupon_rule_time
            in_time_s = time.mktime(time.strptime(args['in_time'], ISOTIMEFORMATS))
            out_time_s = time.mktime(time.strptime(args['out_time'], ISOTIMEFORMATS))
            coupon_msg = get_ecoupon(args['ecoupon_data'])
            ret['park_charge'] = args['charge'] - args['paid_tol']
            coupon_list = []

            if used_coupon and coupon_rule_car == '1':
                ret['used_rights']['ecoupon'] = {'msg': -1}
            elif coupon_rule_time == '1':
                if coupon_msg['times']['tol'] > 0:
                    coupon_msg_tmp = storage_to_dict(coupon_msg['times']['msg'][0])
                    coupon_times_tmp = dict(msg=coupon_msg_tmp, charge=ret['park_charge'], price=ret['park_charge'], actual=ret['park_charge'], calc_in_time=args['in_time'], calc_out_time=args['out_time'])
                    coupon_list.append(coupon_times_tmp)
                    ret['used_rights']['ecoupon'] = coupon_list
                    ret['park_charge'] = 0.0
                elif coupon_msg['money']['tol'] > 0:
                    tmp = 0
                    for elem in coupon_msg['money']['msg']:
                        if elem.value > tmp:
                            tmp = elem.value
                            max_coupon_money = elem

                    coupon_msg_tmp = storage_to_dict(max_coupon_money)
                    charge = ret['park_charge']
                    actual = ret['park_charge']
                    ret['park_charge'] -= tmp
                    if ret['park_charge'] <= 0:
                        ret['park_charge'] = 0
                    else:
                        charge = tmp
                        actual = tmp

                    coupon_money_tmp = dict(msg=coupon_msg_tmp, charge=charge, actual=actual, price=tmp, calc_in_time=args['in_time'], calc_out_time=args['out_time'])
                    coupon_list.append(coupon_money_tmp)
                    ret['used_rights']['ecoupon'] = coupon_list

                elif coupon_msg['hours']['tol'] > 0:
                    tmp = 0
                    for elem in coupon_msg['hours']['msg']:
                        if elem.value > tmp:
                            tmp = elem.value
                            max_coupon_hours = elem

                    last_hour_coupon = list(payrecord.get_hourscoupon_last_calcouttime(args['record_id']))
                    if last_hour_coupon:
                        in_time_tmp = last_hour_coupon[0].calc_out_time.strftime(ISOTIMEFORMATS)
                        in_time_stamp = time.mktime(time.strptime(in_time_tmp, ISOTIMEFORMATS))
                    else:
                        in_time_stamp = time.mktime(time.strptime(args['in_time'], ISOTIMEFORMATS))
                        in_time_stamp_start = in_time_stamp

                    in_time_calc = time.strftime(ISOTIMEFORMATS, time.localtime(in_time_stamp))
                    out_time_calc_stamp = in_time_stamp + max_coupon_hours['value'] * 60
                    out_time_calc = time.strftime(ISOTIMEFORMATS, time.localtime(out_time_calc_stamp))
                    hours_charge = ParkCharge(args['plate_color'], in_time_stamp, out_time_calc_stamp)
                    coupon_msg_tmp = storage_to_dict(max_coupon_hours)
                    charge = ret['park_charge']
                    actual = ret['park_charge']
                    ret['park_charge'] -= hours_charge
                    if ret['park_charge'] < 0:
                        ret['park_charge'] = 0
                    else:
                        charge = hours_charge
                        actual = hours_charge

                    coupon_hours_tmp = dict(msg=coupon_msg_tmp, charge=charge, actual=actual, price=hours_charge, calc_in_time=in_time_calc, calc_out_time=out_time_calc)
                    coupon_list.append(coupon_hours_tmp)
                    ret['used_rights']['ecoupon'] = coupon_list

            elif coupon_rule_time == '2':
                if coupon_msg['times']['tol'] > 0:
                    coupon_msg_tmp = storage_to_dict(coupon_msg['times']['msg'][0])
                    coupon_times_tmp = dict(msg=coupon_msg_tmp, charge=ret['park_charge'], actual=ret['park_charge'], price=ret['park_charge'], calc_in_time=args['in_time'], calc_out_time=args['out_time'])
                    coupon_list.append(coupon_times_tmp)
                    ret['used_rights']['ecoupon'] = coupon_list
                    ret['park_charge'] = 0.0

                elif coupon_msg['money']['tol'] > 0:
                    tmp = ret['park_charge']
                    for elem in coupon_msg['money']['msg']:
                        charge = tmp
                        actual = tmp
                        surplus = tmp - elem.value
                        if surplus > 0:
                            charge = elem.value
                            actual = elem.value

                        coupon_tmp = dict(msg=storage_to_dict(elem), charge=charge, actual=actual, price=elem.value, calc_in_time=args['in_time'], calc_out_time=args['out_time'])
                        coupon_list.append(coupon_tmp)
                        if surplus <= 0:
                            break
                        else:
                            tmp = surplus

                    if surplus >= 0 and coupon_msg['hours']['tol'] > 0:
                        first_hour_flag = 0
                        last_hour_coupon = list(payrecord.get_hourscoupon_last_calcouttime(args['record_id']))
                        if last_hour_coupon:
                            in_time_tmp = last_hour_coupon[0].calc_out_time.strftime(ISOTIMEFORMATS)
                            in_time_stamp = time.mktime(time.strptime(in_time_tmp, ISOTIMEFORMATS))
                            first_hour_flag = 1
                        else:
                            in_time_stamp = time.mktime(time.strptime(args['in_time'], ISOTIMEFORMATS))
                            in_time_stamp_start = in_time_stamp

                        for elem in coupon_msg['hours']['msg']:
                            in_time_calc = time.strftime(ISOTIMEFORMATS, time.localtime(in_time_stamp))
                            out_time_calc_stamp = in_time_stamp + elem['value'] * 60
                            out_time_calc = time.strftime(ISOTIMEFORMATS, time.localtime(out_time_calc_stamp))
                            if first_hour_flag == 1:
                                hours_charge = ParkCharge(args['plate_color'], in_time_stamp, out_time_calc_stamp, 0, 1)
                            else:
                                hours_charge = ParkCharge(args['plate_color'], in_time_stamp, out_time_calc_stamp)
                                first_hour_flag = 1

                            charge = surplus
                            actual = surplus
                            surplus -= hours_charge
                            if surplus > 0:
                                charge = hours_charge
                                actual = hours_charge

                            coupon_tmp = dict(msg=storage_to_dict(elem), charge=charge, actual=actual, price=hours_charge, calc_in_time=in_time_calc, calc_out_time=out_time_calc)
                            coupon_list.append(coupon_tmp)
                            in_time_stamp = out_time_calc_stamp
                            if surplus <= 0:
                                break

                    if surplus <= 0:
                        surplus = 0

                    ret['used_rights']['ecoupon'] = coupon_list
                    ret['park_charge'] = surplus

                elif coupon_msg['hours']['tol'] > 0:
                    surplus = ret['park_charge']
                    first_hour_flag = 0
                    last_hour_coupon = list(payrecord.get_hourscoupon_last_calcouttime(args['record_id']))
                    if last_hour_coupon:
                        in_time_tmp = last_hour_coupon[0].calc_out_time.strftime(ISOTIMEFORMATS)
                        in_time_stamp = time.mktime(time.strptime(in_time_tmp, ISOTIMEFORMATS))
                        first_hour_flag = 1
                    else:
                        in_time_stamp = time.mktime(time.strptime(args['in_time'], ISOTIMEFORMATS))
                        in_time_stamp_start = in_time_stamp

                    for elem in coupon_msg['hours']['msg']:
                        in_time_calc = time.strftime(ISOTIMEFORMATS, time.localtime(in_time_stamp))
                        out_time_calc_stamp = in_time_stamp + elem['value'] * 60
                        out_time_calc = time.strftime(ISOTIMEFORMATS, time.localtime(out_time_calc_stamp))
                        if first_hour_flag == 1:
                            hours_charge = ParkCharge(args['plate_color'], in_time_stamp, out_time_calc_stamp, 0, 1)
                        else:
                            hours_charge = ParkCharge(args['plate_color'], in_time_stamp, out_time_calc_stamp)
                            first_hour_flag = 1

                        charge = surplus
                        actual = surplus
                        print '---------------surplus', surplus
                        print '---------------hours_charge', hours_charge
                        surplus -= hours_charge
                        if surplus > 0:
                            charge = hours_charge
                            actual = hours_charge

                        coupon_tmp = dict(msg=storage_to_dict(elem), charge=charge, actual=actual, price=hours_charge, calc_in_time=in_time_calc, calc_out_time=out_time_calc)
                        coupon_list.append(coupon_tmp)
                        in_time_stamp = out_time_calc_stamp
                        if surplus <= 0:
                            surplus = 0
                            break

                    ret['used_rights']['ecoupon'] = coupon_list
                    ret['park_charge'] = surplus

        if ret['park_charge'] > 0:
            kw['msg'] = ret
            args['charge'] = ret['park_charge']
            return func(args, *arg, **kw)
        else:
            return ret

    return wrapper


def VipEntry(func):
    def wrapper(args, *arg, **kw):
        result = {'used_rights': {}}
        ret_vip = {}
        if args['card_data']:
            print '###AcardEntry'
            print args
            start_t_s = args['card_data'][0]['start_time'].strftime(ISOTIMEFORMATS)
            end_t_s = args['card_data'][0]['end_time'].strftime(ISOTIMEFORMATS)
            start_t = time.mktime(time.strptime(start_t_s, ISOTIMEFORMATS))
            end_t = time.mktime(time.strptime(end_t_s, ISOTIMEFORMATS))
            in_t = time.mktime(time.strptime(args['in_time'], ISOTIMEFORMATS))
            out_t = time.mktime(time.strptime(args['out_time'], ISOTIMEFORMATS))
            plate_color = args['plate_color']
            result['park_time'] = (out_t - in_t) / 3600.0
            card_type = int(args['card_data'][0]['card_type'])
            if result['park_time'] > 0:
                if in_t < start_t and out_t < start_t:
                    result['park_charge'] = ParkCharge(plate_color, in_t, out_t, 0)
                    ret_vip['type'] = 1
                    ret_vip['calc'] = 1
                elif in_t < start_t and out_t > start_t and out_t < end_t:
                    if card_type == 65:
                        result['park_charge'] = ParkCharge(plate_color, in_t, start_t, 0)
                    else:
                        result['park_charge'] = ParkCharge(plate_color, in_t, start_t, 0) + \
                                                ParkCharge(plate_color, start_t, out_t, card_type, 0)
                    ret_vip['type'] = 2
                    ret_vip['calc'] = 2
                elif in_t < start_t and out_t > end_t:
                    if card_type == 65:
                        result['park_charge'] = ParkCharge(plate_color, in_t, start_t + (out_t - end_t), 0)
                    else:
                        result['park_charge'] = ParkCharge(plate_color, in_t, start_t, 0) + \
                                                ParkCharge(plate_color, start_t, end_t, card_type, 0) + \
                                                ParkCharge(plate_color, end_t, out_t, 0, 0)
                    ret_vip['type'] = 3
                    ret_vip['calc'] = 3
                elif in_t > start_t and in_t < end_t and out_t < end_t:
                    if card_type == 65:
                        result['park_charge'] = 0
                    else:
                        result['park_charge'] = ParkCharge(plate_color, in_t, out_t, card_type)
                    ret_vip['type'] = 4
                    ret_vip['calc'] = 4
                elif in_t > start_t and in_t < end_t and out_t > end_t:
                    if card_type == 65:
                        result['park_charge'] = ParkCharge(plate_color, end_t, out_t, 0)
                    else:
                        result['park_charge'] = ParkCharge(plate_color, in_t, end_t, card_type) + \
                                                ParkCharge(plate_color, end_t, out_t, 0)
                    ret_vip['type'] = 5
                    ret_vip['calc'] = 5
                elif in_t > end_t:
                    result['park_charge'] = ParkCharge(plate_color, in_t, out_t, 0)
                    ret_vip['type'] = 6
                    ret_vip['calc'] = 1
                    print type(ret_vip['type'])
                else:
                    pass
            result['park_charge'] = result['park_charge'] - args['paid_tol']
            if out_t > in_t:
                ret_vip['card_remaining_day'] = int((end_t - out_t) / 86400) + 1
            else:
                ret_vip['card_remaining_day'] = None
            ret_vip['start_time'] = start_t_s
            ret_vip['end_time'] = end_t_s

            result['used_rights']['VIP'] = ret_vip
            args['charge'] = result['park_charge']
        else:
            result['park_charge'] = args['charge']

        if result['park_charge'] > 0:
            args['charge'] = result['park_charge']
            kw['msg'] = result
            return func(args, *arg, **kw)
        else:
            return result

    return wrapper


@VipEntry
@EcouponEntry
def BindingEntry(args, **kw):
    print '=' * 50
    print args, kw
    print '=' * 50
    ret = {'used_rights': {}}
    if kw['msg']['used_rights'].has_key('VIP'):
        ret['used_rights']['VIP'] = kw['msg']['used_rights']['VIP']
    if kw['msg']['used_rights'].has_key('ecoupon'):
        ret['used_rights']['ecoupon'] = kw['msg']['used_rights']['ecoupon']

    ret['park_charge'] = args['charge']
    if args['binding_data']:
        print ret
        print '=' * 50
        charge = ret['park_charge']
        actual = ret['park_charge']
        if args['charge'] <= args['binding_data'][0]['limiter']:
            ret['park_charge'] = 0
        else:
            ret['used_rights']['binding']['price'] = 0
            actual = 0

        ret['used_rights']['binding'] = dict(msg=storage_to_dict(args['binding_data'][0]), charge=charge, actual=actual, price=args['charge'], calc_in_time=args['in_time'], calc_out_time=args['out_time'])

    print ret
    print '=' * 50

    return ret
#
#
# if __name__ == "__main__":
#     in_time_str = '2015-05-09 08:40:29'
#     out_time_str = '2015-05-09 09:02:00'
#     in_time = time.mktime(time.strptime(in_time_str, ISOTIMEFORMATS))
#     out_time = time.mktime(time.strptime(out_time_str, ISOTIMEFORMATS))
#     ecoupon_row = list(ecoupon.get_card('A00005'))
#     record_row = list(tmprecords.get("vpr_plate", 'A00005'))
#     binding_car = list(schedules.get_from_binding_cards('A00005'))
#     card_rows = list(cards.get_card_out('A00005'))
#     args_data = {'charge': charge_tmp, 'binding_data': binding_car, 'record_id': record_row[0].in_id, 'ecoupon_data': ecoupon_row, 'card_data': card_rows, 'in_time': in_time_str, 'out_time': out_time_str, 'plate_color': 0, 'paid_tol': 0}
#     ret_data = BindingEntry(args_data)
#     print ret_data
