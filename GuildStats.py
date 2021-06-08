import requests
from requests import Session
import logging
import sys
import time
import datetime


logging.basicConfig(format='%(levelname)s:%(message)s', level=logging.DEBUG)


class WarcraftLogsAPI:

    API_V1 = "https://www.warcraftlogs.com/v1/"

    def __init__(self, api_key=None, guild=None, user_name=None, region=None, server_name=None, start_time=None):
        self.guild = guild
        self.user_name = user_name
        self.region = region
        self.server_name = server_name
        self.api_key = {"api_key": api_key}
        self.start_time = start_time
        self.session = Session()

    # Get all the Public reports for a specific guild
    def get_guild_reports(self):
        api = "reports/guild/{}/{}/{}"
        params = self.api_key
        params.update({'start': self.start_time})
        payload = requests.get(self.API_V1 + api.format(self.guild, self.server_name, self.region), params=self.api_key)
        if payload.status_code != 200:
            print("WARNING - Response code is not 200, Website may be having issues or perhaps the API is dead")
        return payload.json()

    # Gets Report for a specific ID -
    def get_report_details(self, report_id):
        api = "report/fights/{}"
        response = requests.get(self.API_V1 + api.format(report_id), params=self.api_key)
        return response.json()

    # Gets statistics regarding a specific fight (using start and end times) for a report ID
    def get_fight_events(self, view, report_id, death_cutoff=0, start_time=None, end_time=None, difficulty=None):
        if start_time is None or end_time is None:
            print("Start and End times are necessary or else the payload will be empty")
        api = "report/events/{}/{}"
        params = self.api_key
        params.update({'start': start_time, 'end': end_time, 'difficulty': difficulty, 'cutoff': death_cutoff,
                       'hostility': 0})
        payload = requests.get(self.API_V1 + api.format(view, report_id), params=params)
        return payload.json()


client = WarcraftLogsAPI(api_key="1abb81ac8877d2a7834f4bcd2c838f83", guild="Commit", region="US",
                             server_name="sargeras", start_time=1580202000000)


def main():   
    global_raid_team = []
    global_raid_team_dict = {}
    owner_reports = filter_reports_by_owner(client.get_guild_reports(), ["Saylen"])
    # owner_reports = client.get_guild_reports()
    #Filter by date
    report_id_list = retrieve_report_ids(owner_reports)
    test = filter_by_boss(report_id_list, "N'Zoth the Corruptor")
    # Raid team was not filtered because it's a separate portion
    encounters = 0
    for report_id in test['report_ids']:
        encounters = encounters + len(test[report_id]['boss_kills_id'])
        # Specific Fights
        test[report_id]['raid_team'] = raid_team = purge_excess_players(test[report_id]['boss_kills_id'], test[report_id]['raid_team'])
        for fight in test[report_id]['fights']:
            # print(fight)
            events = client.get_fight_events(report_id=report_id, view="deaths", start_time=fight['start_time'],
                                        end_time=fight['end_time'], death_cutoff=3)
            death_list_target_ids = parse_deaths(events)
            for member in raid_team:
                for fightnum in member['fights']:
                    if fightnum['id'] == fight['id']:
                        if not member['name'] in global_raid_team_dict.keys():
                            global_raid_team_dict.update({member['name']: {'encounters_present': 1, 'death_counter': 0}})
                        else:
                            global_raid_team_dict[member['name']]['encounters_present'] += 1
                        if not member['name'] in global_raid_team:
                            global_raid_team.append(member['name'])
                        if death_list_target_ids.count(member['id']) > 0:
                            global_raid_team_dict[member['name']]['death_counter'] += death_list_target_ids.count(member['id'])
    print(encounters)
    print(global_raid_team_dict.update({"global_raid_name_list": global_raid_team}))
    print(global_raid_team)
    for item in global_raid_team_dict['global_raid_name_list']:
        # print("Player: %s Total Encounters: %s Total Deaths: %s Deaths/Encounters: %s" % (item, global_raid_team_dict[item]['encounters_present'], global_raid_team_dict[item]['death_counter'], find_ratio(global_raid_team_dict[item]['death_counter'], global_raid_team_dict[item]['encounters_present'])))
        global_raid_team_dict[item].update({"death_ratio": find_ratio(global_raid_team_dict[item]['death_counter'], global_raid_team_dict[item]['encounters_present'])})
    print(global_raid_team_dict)
    new_dict = {}
    ratio_list = []
    for item in global_raid_team_dict['global_raid_name_list']:
        if global_raid_team_dict[item]['encounters_present'] < 5:
            ratio_list.append(global_raid_team_dict[item]['death_ratio'])
            string_order = ("|| Player: %s || Total Encounters: %s || Total Deaths: %s || Death Ratio: %s ||" % (item, global_raid_team_dict[item]['encounters_present'], global_raid_team_dict[item]['death_counter'], str(round(global_raid_team_dict[item]['death_ratio'], 5))))
            new_dict.update({global_raid_team_dict[item]['death_ratio']: string_order})
    new_dict.update({'ratio_list': ratio_list})
    ratio_list.sort()
    print(new_dict)
    for item in ratio_list:
        print(new_dict[item])
    sys.exit(0)


def find_ratio(a, b):
    try:
        return float(a/b)
    except ZeroDivisionError:
        return "Invalid"


def parse_deaths(event_json):
    death_log = []
    for event in event_json['events']:
        if event['type'] == "death":
            death_log.append(event['targetID'])
    return death_log



# Raid team is specific per log, therefore there are extras if the same log had multiple fights, need to clean up
def purge_excess_players(boss_id_list, raid_team):
    # Remove fights that we don't care for per player
    delete_list = []
    for member in raid_team:
        fight_delete = []
        for fight_num in member['fights']:
            if fight_num['id'] not in boss_id_list:
                fight_delete.append(fight_num)
        for delfight in fight_delete:
            member['fights'].remove(delfight)
    # Now we purge the players who in the fights we care for
    for member in raid_team:
        if len(member['fights']) < 1:
            delete_list.append(member)
    for name in delete_list:
        raid_team.remove(name)
    return raid_team






# Reports by a specific Owner ex. Saylen
def filter_reports_by_owner(report_list, owner_name=None):
    payload = []
    for item in report_list:
        if owner_name is not None:
            if item['owner'] in owner_name:
                payload.append(item)
    return payload


# Parse IDs
def retrieve_report_ids(report_list):
    payload = []
    print()
    for report in report_list:
        payload.append(report['id'])
    return payload


# Filter boss by name and difficulty
def filter_by_boss(report_id_list, boss_name, difficulty=5):
    payload = {}
    accurate_report_id = []
    for report_id in report_id_list:
        found = False
        fights = []
        boss_id_list = []
        inner_dict = {}
        data_set = client.get_report_details(report_id)
        for fight in data_set['fights']:
            if fight['boss'] == 0:
                continue
            if fight['name'] == boss_name:
                try:
                    if fight['difficulty'] != difficulty or fight['zoneDifficulty'] != difficulty:
                        continue
                    # This is a sus edge case, without some heroic kills are included.
                except KeyError:
                    # For some reason all the data isn't always there, zonedifficulty or difficulty can be missing
                    # but its still  a valid pull
                    logging.warning("=======================================Error=======================================")
                    logging.warning("Difficulty/zonedifficulty tag not there, very sus looks like twin and twodie vented for the below fights")
                    logging.warning("For some reason all the data isn't always there, zonedifficulty or difficulty can be "
                          "missing but its still a valid pull")
                    logging.warning("Fight in question: %s" % fight)
                    logging.warning("Report Id in question: %s" % report_id)
                    logging.warning("===================================================================================")
                    pass
                found = True
                fights.append(fight)
                boss_id_list.append(fight['id'])
                inner_dict.update({'fights': fights})
                accurate_report_id.append(report_id)
        if not found:
            continue
        boss_id_list = filter_raidteam_mythic20(encounter_list=boss_id_list,
                                 raid_team=data_set['friendlies'])
        inner_dict.update({'raid_team': data_set['friendlies']})
        inner_dict.update({'boss_kills_id': boss_id_list})
        payload.update({report_id: inner_dict})
    payload.update({'report_ids': list(dict.fromkeys(accurate_report_id))})
    return payload


def filter_raidteam_mythic20(encounter_list, raid_team):
    encounter_list_cleanup = []
    for encounter in encounter_list:
        if raid_size(raid_team, encounter) == 20:
            encounter_list_cleanup.append(encounter)
    # Idunno if its worth deleting any data, you already have it
    # for player in raid_team:
    #     for encounter in player['fights']:
    #         if encounter['id'] not in encounter_list_cleanup:
    #             player['fights'].remove(encounter)
    return encounter_list_cleanup


def raid_size(raid_team, encounter_no):
    attendance_count = 0
    for player in raid_team:
        for encounter_id in player['fights']:
            if encounter_id == {'id': encounter_no}:
                attendance_count = attendance_count + 1
    return attendance_count



if __name__ == '__main__':
    main()
