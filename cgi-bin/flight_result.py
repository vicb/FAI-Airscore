from calcUtils import get_datetime
from route import rawtime_float_to_hms, in_semicircle, distance_flown
from myconn import Database
import jsonpickle, json
from mapUtils import checkbbox


"""
contains Flight_result class.
contains statistics about a flight with regards to a task.

Methods:
    from_fsdb
    check_flight - check flight against task and record results (times, distances and leadout coeff)
    store_result - write result to DB (tblTaskResult)
    store_result_test - write result to DB in test mode(tblTaskResult_test)
	store_result_json - not needed, think we can delete
	to_geojson_result - create json file containing tracklog (split into preSSS, preGoal and postGoal), Thermals, bounds and result obj
	save_result_file - save the json file.
"""


class Flight_result:
    """Set of statistics about a flight with respect a task.
    Attributes:
        Start_time:     time the task was started . i.e relevant start gate. (local time)
        SSS_time:       array of time(s) the pilot started, i.e. crossed the start line (local time)
        Waypoints achieved: the last waypoint achieved by the pilot, SSS, ESS, Goal or a waypoint number (wp1 is first wp after SSS)
        ESS_time:       the time the pilot crossed the ESS (local time)
        total_time:     the length of time the pilot took to complete the course. ESS- Start_time (for Race) or ESS - SSS_time (for elapsed)
        Fixed_LC:       fixed part of Lead_coeff, indipendent from other tracks
        Lead_coeff:     lead points coeff (for GAP based systems), sum of Fixed_LC and variable part calcullated during scoring
        """

    def __init__(self, Pilot_Start_time=None, SSS_time=0, Start_time_str='', SSS_time_str='',
                 Best_waypoint_achieved='No waypoints achieved', ESS_time_str='', total_time_str=None, ESS_time=None,
                 last_time=None,
                 total_time=None, Fixed_LC=0, Lead_coeff=0, Distance_flown=0, Stopped_time=None, Stopped_altitude=0,
                 Jumped_the_gun=None):
        """

        :type Lead_coeff: int
        """
        self.Start_time_str = Start_time_str
        self.SSS_time_str = SSS_time_str
        self.Pilot_Start_time = Pilot_Start_time
        self.SSS_time = SSS_time
        self.Best_waypoint_achieved = Best_waypoint_achieved
        self.Waypoints_achieved = []
        self.ESS_time = ESS_time
        self.total_time = total_time
        self.last_time = last_time
        self.ESS_time_str = ESS_time_str
        self.total_time_str = total_time
        self.Fixed_LC = Fixed_LC
        self.Lead_coeff = Lead_coeff
        self.distance_flown = Distance_flown
        self.Stopped_time = Stopped_time
        self.Stopped_altitude = Stopped_altitude
        self.Jumped_the_gun = Jumped_the_gun
        self.Score = 0
        self.Total_distance = 0
        self.Departure_score = 0
        self.Arrival_score = 0
        self.distance_score = 0
        self.Time_score = 0
        self.Penalty = 0
        self.Comment = None
        self.ext_id = None
        self.pil_id = None
        self.result_type = 'lo'
        self.goal_time = None
        self.SS_distance = None

    @property
    def speed(self):
        if self.ESS_time and self.SS_distance:
            return (self.SS_distance / 1000) / (self.total_time / 3600)
        else:
            return 0

    @classmethod
    def from_fsdb(cls, res, dep=None, arr=None):
        """ Creates Results from FSDB FsPartecipant element, which is in xml format.
            Unfortunately the fsdb format isn't published so much of this is simply an
            exercise in reverse engineering.
        """
        from datetime import timedelta

        result = cls()
        result.ext_id = int(res.get('id'))
        if res.find('FsResult') is not None:
            '''reading flight data'''
            r = res.find('FsResult')
            # result['rank'] = int(r.get('rank'))
            result.Score = int(r.get('points'))
            result.Total_distance = float(r.get('distance')) * 1000  # in meters
            result.distance_flown = float(r.get('real_distance')) * 1000  # in meters
            # print ("start_ss: {}".format(r.get('started_ss')))
            result.Pilot_Start_time = get_datetime(r.get('started_ss')).time() if r.get(
                'started_ss') is not None else None
            result.SSS_time = float(r.get('ss_time_dec_hours'))
            if result.SSS_time > 0:
                result.ESS_time = get_datetime(r.get('finished_ss')).time()
                print(" ESS Time: {}".format(result.ESS_time))
                print(" * time but not goal: {}".format(r.get('got_time_but_not_goal_penalty')))
                if r.get('got_time_but_not_goal_penalty') == 'False':
                    print(" * pilot made Goal! *")
                    '''pilot did make goal, we need to put a time in tarGoal
                        I just put a time 10 minutes after ESS time'''
                    result.goal_time = (get_datetime(r.get('finished_ss')) + timedelta(minutes=10)).time()
                    print("    fake goal time: {}".format(result.goal_time))
            else:
                result.ESS_time = None
            result.Stopped_altitude = int(r.get('last_altitude_above_goal'))
            result.distance_score = float(r.get('distance_points'))
            result.Time_score = float(r.get('time_points'))
            result.Penalty = int(r.get('penalty_points'))
            result.Comment = r.get('penalty_reason')
            if dep is 'on':
                result.Departure_score = float(r.get('departure_points'))
            elif dep is 'leadout':
                result.Departure_score = float(r.get('leading_points'))
            else:
                result.Departure_score = 0  # not necessary as it it initialized to 0
            result.Arrival_score = float(r.get('arrival_points')) if arr is 'on' else 0
        else:
            '''pilot has no recorded flight'''
            result.result_type = 'abs'
        # print ("Result in obj: id {} was: {} start: {} end: {} points: {} ".format(result.ext_id, result.result_type, result.Start_time, result.ESS_time, result.Score))

        return result

    @classmethod
    def read_from_db(cls, res_id, test=0):
        """reads result from database"""
        query = (""" SELECT
                        *
                    FROM
                        ResultView
                    WHERE
                        tarPk = {}
                    LIMIT 1
                """.format(res_id))
        if test:
            print('Result query:')
            print(query)

        with Database() as db:
            # get the task details.
            t = db.fetchone(query)
        if t is None:
            print('Not a valid flight')
            return
        else:
            result = cls()
            result.pil_id = t['pilPk']
            result.Pilot_Start_time = t['tarStart']
            result.SSS_time = t['tarSS']
            result.ESS_time = t['tarES']
            result.goal_time = t['tarGoal']
            result.total_time = t['tarLastTime'] - t['tarStart']
            result.Fixed_LC = t['tarLeadingCoeff2']
            result.distance_flown = t['tarDistance']
            result.Stopped_altitude = t['tarLastAltitude']
            result.Jumped_the_gun = None
            result.Score = t['tarScore']
            result.Total_distance = t['tarDistance']
            result.Departure_score = t['tarDepartureScore']
            result.Arrival_score = t['tarArrivalScore']
            result.distance_score = t['tarDistanceScore']
            result.Time_score = t['tarSpeedScore']
            result.Penalty = t['tarPenalty']
            result.Comment = t['tarComment']
            result.ext_id = None
            result.result_type = 'lo'
            return result

    @classmethod
    def check_flight(cls, Flight, Task, formula_parameters, min_tol_m=0):
        """ Checks a Flight object against the task.
            Args:
                   Flight: a Flight object
                   Task: a Taskm object
                   min_tol: minimum tolerance in meters, default is 0
            Returns:
                    a list of GNSSFixes of when turnpoints were achieved.
        """
        from route import start_made_civl, tp_made_civl, tp_time_civl

        result = cls()
        tolerance = Task.tolerance
        time_offset = Task.time_offset  # local time offset for result times (SSS and ESS)
        goal_alt = Task.goal_altitude   # Goal Altitude, will be used in Stooped_altitude above goal

        # result.SSS_time = Task.start_time

        if not Task.optimised_turnpoints:
            Task.calculate_optimised_task_length()
        distances2go = Task.distances_to_go  # Total task Opt. Distance, in legs list
        best_dist_to_ess = [Task.SS_distance]  # Best distance to ESS, for LC calculation
        waypoint = 1  # for report purpouses
        # proceed_to_start    = False               # check position to start, probably not necessary in new logic
        t = 0  # turnpoint pointer
        started = False  # check if pilot has a valid start fix

        for i in range(len(Flight.fixes) - 1):
            '''Get two consecutive trackpoints as needed to use FAI / CIVL rules logic
            '''
            fix = Flight.fixes[i]
            next = Flight.fixes[i + 1]
            # print('fix {} | waypoint {} \n'.format(i, t))
            # print('type {} \n'.format(Task.turnpoints[t].type))
            # print('* in fix {} pilot is flying: {}'.format(fix, bool(fix.flying)))

            # fix.rawtime_local = fix.rawtime + time_offset  #local time for result times (SSS and ESS)
            result.Stopped_time = fix.rawtime

            '''handle stopped task'''
            maxtime = None
            if Task.stopped_time is not None and result.ESS_time is None:
                if formula_parameters.stopped_elapsed_calc == 'shortest_time' and Task.last_start_time:
                    maxtime = (Task.stopped_time - Task.last_start_time)

                if (next.rawtime > Task.stopped_time
                        or
                        (maxtime is not None and result.SSS_time is not None
                         and (next.rawtime > result.SSS_time + maxtime))):
                    result.Stopped_altitude = max(fix.gnss_alt,
                                                  fix.press_alt) - goal_alt  # check the rules on this point..which alt to
                    break

            '''check if pilot has arrived in goal (last turnpoint) so we can stop.'''
            if t >= len(Task.turnpoints):
                break

            '''check if task deadline has passed'''
            if Task.task_deadline < next.rawtime:
                # Task has ended
                break

            '''check if start closing time passed and pilot did not start'''
            if (Task.start_close_time and (Task.start_close_time < fix.rawtime) and not started):
                # start closed
                break

            '''check tp type is known'''
            if Task.turnpoints[t].type not in ('launch', 'speed', 'waypoint', 'endspeed', 'goal'):
                assert False, "Unknown turnpoint type: %s" % Task.turnpoints[t].type

            '''launch turnpoint managing'''
            if Task.turnpoints[t].type == "launch":
                # not checking launch yet
                if Task.check_launch == 'on':
                    # Set radius to check to 200m (in the task def it will be 0)
                    # could set this in the DB or even formula if needed..???
                    Task.turnpoints[t].radius = 200  # meters
                    if Task.turnpoints[t].in_radius(fix, tolerance, min_tol_m):
                        result.Waypoints_achieved.append(["Left Launch", fix.rawtime])  # pilot has achieved turnpoint
                        t += 1

                else:
                    t += 1

            # to do check for restarts for elapsed time tasks and those that allow jump the gun
            # if started and Task.task_type != 'race' or result.Jumped_the_gun is not None:

            '''start turnpoint managing'''
            '''given all n crossings for a turnpoint cylinder, sorted in ascending order by their crossing time,
            the time when the cylinder was reached is determined.
            turnpoint[i] = SSS : reachingTime[i] = crossing[n].time
            turnpoint[i] =? SSS : reachingTime[i] = crossing[0].time

            We need to check start in 3 cases:
            - pilot has not started yet
            - race has multiple starts
            - task is elapsed time
            '''

            if (((Task.turnpoints[t].type == "speed" and not started)
                 or
                 (Task.turnpoints[t - 1].type == "speed" and (Task.SS_interval or Task.task_type == 'ELAPSED TIME')))
                    and
                    (fix.rawtime >= (Task.start_time - formula_parameters.max_jump_the_gun))
                    and
                    (not (Task.start_close_time) or (fix.rawtime <= Task.start_close_time))):

                # we need to check if it is a restart, so to use correct tp
                if Task.turnpoints[t - 1].type == "speed":
                    SS_tp = Task.turnpoints[t - 1]
                    restarting = True
                else:
                    SS_tp = Task.turnpoints[t]
                    restarting = False

                if start_made_civl(fix, next, SS_tp, tolerance, min_tol_m):
                    time = round(tp_time_civl(fix, next, SS_tp), 0)
                    result.Waypoints_achieved.append(["SSS", time])  # pilot has started
                    started = True
                    result.Fixed_LC = 0  # resetting LC to last start time
                    if not restarting:
                        t += 1

            if started:
                '''Turnpoint managing'''
                if (Task.turnpoints[t].shape == 'circle'
                        and Task.turnpoints[t].type in ('endspeed', 'waypoint')):
                    tp = Task.turnpoints[t]
                    if tp_made_civl(fix, next, tp, tolerance, min_tol_m):
                        time = round(tp_time_civl(fix, next, tp), 0)
                        name = 'ESS' if tp.type == 'endspeed' else 'TP{:02}'.format(waypoint)
                        # result.Best_waypoint_achieved = 'waypoint ' + str(waypoint) + ' made'
                        result.Waypoints_achieved.append([name, time])  # pilot has achieved turnpoint
                        waypoint += 1
                        t += 1

                if Task.turnpoints[t].type == 'goal':
                    goal_tp = Task.turnpoints[t]
                    if ((goal_tp.shape == 'circle' and tp_made_civl(fix, next, goal_tp, tolerance, min_tol_m))
                            or (goal_tp.shape == 'line' and (in_semicircle(Task, Task.turnpoints, t, fix)
                                                             or in_semicircle(Task, Task.turnpoints, t, next)))):
                        result.Waypoints_achieved.append(['Goal', next.rawtime])  # pilot has achieved turnpoint
                        break

            '''update result data
            Once launched, distance flown should be max result among:
            - previous value;
            - optimized dist. to last turnpoint made;
            - total optimized distance minus opt. distance from next wpt to goal minus dist. to next wpt;
            '''
            if t > 0:
                result.distance_flown = max(result.distance_flown, (distances2go[0] - distances2go[t-1]),
                                        distance_flown(next, t, Task.optimised_turnpoints, Task.turnpoints[t], distances2go))
            # print('fix {} | Dist. flown {} | tp {}'.format(i, round(result.distance_flown, 2), t))

            '''Leading coefficient
                LC = taskTime(i)*(bestDistToESS(i-1)^2 - bestDistToESS(i)^2 )
                i : i ? TrackPoints In SS'''
            if started and not any(e[0] == 'ESS' for e in result.Waypoints_achieved):
                pilot_start_time = max([e[1] for e in result.Waypoints_achieved if e[0] == 'SSS'])
                taskTime = next.rawtime - pilot_start_time
                best_dist_to_ess.append(Task.opt_dist_to_ESS - result.distance_flown)
                result.Fixed_LC += formula_parameters.coef_func(taskTime, best_dist_to_ess[0], best_dist_to_ess[1])
                # print('    best dist. to ESS {} : {} | Time {} | LC: {}'.format(round(best_dist_to_ess[0],1),round(best_dist_to_ess[1],1),taskTime, result.Fixed_LC))
                best_dist_to_ess.pop(0)

        # result.last_time = min(Flight.fixes[-1].rawtime, result.goal_time, Task.task_deadline, Task.stopped_time)
        # print('last_time: {} | last considered fix time: {}'.format(result.last_time, next.rawtime))

        '''final results'''
        if started:
            '''start time
            if race, the first times
            if multistart, the time of the last gate
            il elapsed time, the time of last fix'''
            if Task.task_type == 'RACE':
                if not Task.SS_interval:
                    result.SSS_time = Task.start_time
                    result.SSS_time_str = (("%02d:%02d:%02d") % rawtime_float_to_hms(Task.start_time + time_offset))
                    result.Pilot_Start_time = min([e[1] for e in result.Waypoints_achieved if e[0] == 'SSS'])
                else:
                    start_num = int((Task.start_close_time - Task.start_time) / (Task.SS_interval * 60))
                    gate = Task.start_time + ((Task.SS_interval * 60) * start_num)  # last gate
                    while gate >= Task.start_time:
                        if any([e for e in result.Waypoints_achieved if e[0] == 'SSS' and e[1] >= gate]):
                            result.SSS_time = gate
                            result.SSS_time_str = (
                                    ("%02d:%02d:%02d") % rawtime_float_to_hms(gate + time_offset))
                            result.Pilot_Start_time = min(
                                [e[1] for e in result.Waypoints_achieved if e[0] == 'SSS' and e[1] >= gate])
                            break
                        gate -= Task.SS_interval * 60

            elif Task.task_type == 'ELAPSED TIME':
                result.Pilot_Start_time = max([e[1] for e in result.Waypoints_achieved if e[0] == 'SSS'])
                result.SSS_time = result.Pilot_Start_time
                result.SSS_time_str = (("%02d:%02d:%02d") % rawtime_float_to_hms(result.SSS_time + time_offset))

            result.Start_time_str = (("%02d:%02d:%02d") % rawtime_float_to_hms(result.SSS_time + time_offset))

            '''ESS Time'''
            if any(e[0] == 'ESS' for e in result.Waypoints_achieved):
                result.ESS_time = min([e[1] for e in result.Waypoints_achieved if e[0] == 'ESS'])
                result.ESS_time_str = (("%02d:%02d:%02d") % rawtime_float_to_hms(result.ESS_time + time_offset))
                result.total_time = result.ESS_time - result.SSS_time
                result.total_time_str = (("%02d:%02d:%02d") % rawtime_float_to_hms(result.ESS_time - result.SSS_time))

                '''Distance flown'''
                ''' ?p:p?PilotsLandingBeforeGoal:bestDistancep = max(minimumDistance, taskDistance-min(?trackp.pointi shortestDistanceToGoal(trackp.pointi)))
                    ?p:p?PilotsReachingGoal:bestDistancep = taskDistance
                '''
                if any(e[0] == 'Goal' for e in result.Waypoints_achieved):
                    result.distance_flown = distances2go[0]
                    result.goal_time = min([e[1] for e in result.Waypoints_achieved if e[0] == 'Goal'])

        result.Best_waypoint_achieved = str(result.Waypoints_achieved[-1][0]) if result.Waypoints_achieved else None

        # if result.ESS_time is None: # we need to do this after other operations
        #     result.Fixed_LC += formula_parameters.coef_landout((Task.task_deadline - Task.start_time),((Task.opt_dist_to_ESS - result.distance_flown) / 1000))
        # print('    * Did not reach ESS LC: {}'.format(result.Fixed_LC))

        result.Fixed_LC = formula_parameters.coef_func_scaled(result.Fixed_LC, Task.opt_dist_to_ESS)
        # print('    * Final LC: {} \n'.format(result.Fixed_LC))
        return result

    def store_result_test(self, traPk, tasPk):

        goal_time = 0 if self.goal_time is None else self.goal_time
        endss = 0 if self.ESS_time is None else self.ESS_time

        # print("turnponts", len(self.Waypoints_achieved))
        query = "DELETE FROM tblTaskResult_test where traPk=%s and tasPk=%s"
        params = [traPk, tasPk]
        with Database() as db:
            db.execute(query, params)

        # query = "INSERT INTO tblTaskResult_test (" \
        #         "tasPk, traPk, tarDistance, tarSpeed, tarStart, tarGoal, tarSS, tarES, tarTurnpoints, " \
        #         "tarLeadingCoeff, tarPenalty, tarComment, tarLastAltitude, tarLastTime ) " \
        #         "VALUES ({}, {}, {}, {}, {}, {}, {}, {}, {}, {}, {}, {}, {}, {})".format(tasPk, traPk, self.distance_flown, self.speed, self.Pilot_Start_time, self.goal_time, self.SSS_time, endss, len(self.Waypoints_achieved), self.Fixed_LC, self.Penalty, self.Comment, self.Stopped_altitude, self.Stopped_time)
        # print(query)

        query = "INSERT INTO tblTaskResult_test ( " \
                "tasPk, traPk, tarDistance, tarSpeed, tarStart, tarGoal, tarSS, tarES, tarTurnpoints, " \
                "tarLeadingCoeff2, tarPenalty, tarLastTime ) " \
                "VALUES ( %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s )"
        # , #%s, %s, %s)"
        num_wpts = len(self.Waypoints_achieved)
        params = [tasPk, traPk, self.distance_flown, self.speed, self.Pilot_Start_time, goal_time, self.SSS_time, endss,
                  num_wpts, self.Fixed_LC, self.Penalty,
                  self.Stopped_time]  # , self.Comment, self.Stopped_altitude, self.Stopped_time]

        with Database() as db:
            r = db.execute(query, params)
        print(r)

    # def store_result(self, traPk, tasPk):
    #     from collections import Counter
    #
    #     if not self.goal_time: self.goal_time = 0
    #     endss = 0 if not self.ESS_time else self.ESS_time
    #     num_wpts = len(Counter(el[0] for el in self.Waypoints_achieved))
    #
    #     query = "DELETE FROM `tblTaskResult` WHERE `traPk`=%s and `tasPk`=%s"
    #     params = [traPk, tasPk]
    #     with Database() as db:
    #         db.execute(query, params)
    #
    #     query = """INSERT INTO `tblTaskResult` (
    #             `tasPk`, `traPk`, `tarDistance`, `tarSpeed`, `tarStart`, `tarGoal`, `tarSS`, `tarES`, `tarTurnpoints`,
    #             `tarLeadingCoeff2`, `tarLeadingCoeff`, `tarPenalty`, `tarLastAltitude`, `tarLastTime` )
    #             VALUES ( %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s ) """
    #
    #     params = [tasPk, traPk, self.distance_flown, self.speed, self.Pilot_Start_time, self.goal_time, self.SSS_time,
    #               endss, num_wpts,
    #               self.Fixed_LC, self.Lead_coeff, self.Penalty, self.Stopped_altitude,
    #               self.Stopped_time]  # , self.Comment, self.Stopped_altitude, self.Stopped_time]

    def store_result(self, task_id, track_id = None):
        ''' stores new calculated results to db
            if track_id is not given, it inserts a new result
            else it updates existing one '''
        from collections import Counter

        if not self.goal_time: self.goal_time = 0
        endss = 0 if not self.ESS_time else self.ESS_time
        num_wpts = len(Counter(el[0] for el in self.Waypoints_achieved))

        if track_id:
            query = """ UPDATE
                            `tblTaskResult`
                        SET
                            `tarDistance`       = %s,
                            `tarSpeed`          = %s,
                            `tarStart`          = %s,
                            `tarGoal`           = %s,
                            `tarSS`             = %s,
                            `tarES`             = %s,
                            `tarTurnpoints`     = %s,
                            `tarLeadingCoeff2`  = %s,
                            `tarLastAltitude`   = %s,
                            `tarLastTime`       = %s
                        WHERE
                            `tarPk` = %s
                    """
            params = [self.distance_flown, self.speed, self.Pilot_Start_time, self.goal_time, self.SSS_time,
                      endss, num_wpts, self.Fixed_LC, self.Stopped_altitude, self.Stopped_time, track_id]


        else:       #should not be possible, as we wouldn't have track file stored
            query = """ INSERT INTO `tblTaskResult`(
                            `pilPk`,
                            `tasPk`,
                            `tarDistance`,
                            `tarSpeed`,
                            `tarStart`,
                            `tarGoal`,
                            `tarSS`,
                            `tarES`,
                            `tarTurnpoints`,
                            `tarLeadingCoeff2`,
                            `tarLastAltitude`,
                            `tarLastTime`
                        )
                        VALUES( %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s )"""
            params = [self.pil_id, task_id, self.distance_flown, self.speed, self.Pilot_Start_time, self.goal_time, self.SSS_time,
                      endss, num_wpts, self.Fixed_LC, self.Stopped_altitude, self.Stopped_time]

        with Database() as db:
            db.execute(query, params)

    def store_result_json(self):
        json.dump(self)

    def to_geojson_result(self, track, task, second_interval=5):
        """Dumps the flight to geojson format used for mapping.
        Contains tracklog split into pre SSS, pre Goal and post goal parts, thermals, takeoff/landing,
        result object, waypoints achieved, and bounds

        second_interval = resolution of tracklog. default one point every 5 seconds. regardless it will
                            keep points where waypoints were achieved.
        returns the Json string."""

        from geojson import Point, Feature, FeatureCollection, MultiLineString

        features = []
        toff_land = []
        thermals = []

        min_lat = track.flight.fixes[0].lat
        min_lon = track.flight.fixes[0].lon
        max_lat = track.flight.fixes[0].lat
        max_lon = track.flight.fixes[0].lon
        bbox = [[min_lat, min_lon], [max_lat, max_lon]]

        takeoff = Point((track.flight.takeoff_fix.lon, track.flight.takeoff_fix.lat))
        toff_land.append(Feature(geometry=takeoff, properties={"TakeOff": "TakeOff"}))
        landing = Point((track.flight.landing_fix.lon, track.flight.landing_fix.lat))
        toff_land.append(Feature(geometry=landing, properties={"Landing": "Landing"}))

        for thermal in track.flight.thermals:
            thermals.append((thermal.enter_fix.lon, thermal.enter_fix.lat,
                             f'{thermal.vertical_velocity():.1f}m/s gain:{thermal.alt_change():.0f}m'))

        pre_sss = []
        pre_goal = []
        post_goal = []
        waypoint_achieved = []

        #if the pilot did not make goal, goal time will be None. set to after end of track to avoid issues.
        if not self.goal_time:
            goal_time= track.flight.fixes[-1].rawtime + 1
        else:
            goal_time = self.goal_time

        # if the pilot did not make SSS then it will be 0, set to task start time.
        if self.SSS_time==0:
            SSS_time = task.start_time
        else:
            SSS_time = self.SSS_time

        waypoint = 0
        lastfix = track.flight.fixes[0]
        for fix in track.flight.fixes:
            bbox = checkbbox(fix.lat, fix.lon, bbox)
            keep = False
            if fix.rawtime >= lastfix.rawtime + second_interval:
                keep = True
                lastfix = fix

            if fix.rawtime == self.Waypoints_achieved[waypoint][1]:
                time = (("%02d:%02d:%02d") % rawtime_float_to_hms(fix.rawtime + task.time_offset))
                waypoint_achieved.append((fix.lon, fix.lat, fix.gnss_alt, fix.press_alt, self.Waypoints_achieved[waypoint][0],
                                          f'{self.Waypoints_achieved[waypoint][0]} '
                                          f'gps alt:{fix.gnss_alt:.0f}m '
                                          f'baro alt{fix.press_alt:.0f}m '
                                          f'time: {time}'))
                keep = True
                if waypoint < len(self.Waypoints_achieved)-1:
                    waypoint += 1

            if keep:
                if fix.rawtime <= SSS_time:
                    pre_sss.append((fix.lon, fix.lat, fix.gnss_alt, fix.press_alt))
                if fix.rawtime >= SSS_time and fix.rawtime <= goal_time:
                    pre_goal.append((fix.lon, fix.lat, fix.gnss_alt, fix.press_alt))
                if fix.rawtime >= goal_time:
                    post_goal.append((fix.lon, fix.lat, fix.gnss_alt, fix.press_alt))

        route_multilinestring = MultiLineString([pre_sss])
        features.append(Feature(geometry=route_multilinestring, properties={"Track": "Pre_SSS"}))
        route_multilinestring = MultiLineString([pre_goal])
        features.append(Feature(geometry=route_multilinestring, properties={"Track": "Pre_Goal"}))
        route_multilinestring = MultiLineString([post_goal])
        features.append(Feature(geometry=route_multilinestring, properties={"Track": "Post_Goal"}))

        feature_collection = FeatureCollection(features)

        data = {'tracklog': feature_collection, 'thermals': thermals, 'takeoff_landing': toff_land,
                'result': jsonpickle.dumps(self), 'bounds': bbox, 'waypoint_achieved': waypoint_achieved}

        return data


    def save_result_file(self, data, trackid):
        """save result file in the correct folder as defined by DEFINES"""

        from os import path, makedirs
        import Defines
        res_path = Defines.MAPOBJDIR + 'tracks/'

        """check if directory already exists"""
        if not path.isdir(res_path):
            makedirs(res_path)
        """creates a name for the track
        name_surname_date_time_index.igc
        if we use flight date then we need an index for multiple tracks"""

        filename = 'result_'+str(trackid)+ '.json'
        fullname = path.join(res_path, filename)
        """copy file"""
        try:
            with open(fullname, 'w') as f:
                json.dump(data, f)
            return fullname
        except:
            print('Error saving file:', fullname)
