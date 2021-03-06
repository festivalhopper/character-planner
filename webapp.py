from collections import defaultdict
from flask import Flask, render_template, request

from wow_dps_sim.entities import Player
from wow_dps_sim.helpers import from_module_import_x
from wow_dps_sim.scraper import Scraper
from wow_dps_sim.sim import do_sim
from wow_dps_sim.stats import Stats

app = Flask(__name__)


@app.route('/', methods=['GET'])
def show_init():
    return render_template('init.html')


@app.route('/main', methods=['GET'])
def show_main():
    return render_template('main.html', **(request.args.to_dict()))


@app.route('/main/calc_stats', methods=['POST'])
def calc_stats():
    request_data = request.json

    race = request_data['race']
    class_ = request_data['class']
    spec = request_data[f"spec_{request_data['class']}"]

    expansion = request_data['expansion']
    scraper = Scraper(request_data['scraper_item_db'], expansion)
    items = _fetch_items(scraper, request_data)

    socket_stats, _ = _fetch_socket_stats(request_data)

    ExpansionSpecificStats = from_module_import_x('wow_dps_sim.expansion.' + expansion + '.stats', 'Stats')
    stats = Stats(expansion)
    unbuffed_stats = stats.calc_unbuffed_stats(race, class_, spec, items, socket_stats)
    unbuffed_base_stats, unbuffed_primary_stats, unbuffed_secondary_stats = ExpansionSpecificStats.get_displayable_stats(items, unbuffed_stats)

    faction = request_data['faction']
    buffed_stats = stats.calc_partial_buffed_permanent_stats(faction, race, class_, spec, items, socket_stats)
    buffed_stats = ExpansionSpecificStats.apply_berserker_stance_flat_effects(buffed_stats)
    buffed_stats = ExpansionSpecificStats.apply_berserker_stance_percentage_effects(buffed_stats)
    buffed_stats = stats.finalize_buffed_stats(faction, race, class_, spec, buffed_stats)
    buffed_base_stats, buffed_primary_stats, buffed_secondary_stats = ExpansionSpecificStats.get_displayable_stats(items, buffed_stats)

    return render_template(
        'stats.html',
        unbuffed_base_stats=unbuffed_base_stats,
        unbuffed_primary_stats=unbuffed_primary_stats,
        unbuffed_secondary_stats=unbuffed_secondary_stats,
        buffed_stats=str(buffed_stats),
        buffed_base_stats=buffed_base_stats,
        buffed_primary_stats=buffed_primary_stats,
        buffed_secondary_stats=buffed_secondary_stats,
    )


@app.route('/main/sim', methods=['POST'])
def sim():
    request_data = request.json
    faction = request_data['faction']
    race = request_data['race']
    class_ = request_data['class']
    spec = request_data[f"spec_{request_data['class']}"]

    expansion = request_data['expansion']
    scraper = Scraper(request_data['scraper_item_db'], expansion)
    items = _fetch_items(scraper, request_data)

    socket_stats, meta_socket_active = _fetch_socket_stats(request_data)

    player = Player(
        faction, race, class_, spec, items, meta_socket_active,
        expansion=expansion, socket_stats=socket_stats
    )
    result, stat_weights = do_sim(expansion, player)

    return str(result)
    # return f'{result}\nStat weights: {stat_weights}\n'


def _fetch_items(scraper, request_data):
    item_slot_id_tuples = [(form_key.replace('item_', ''), form_value) for form_key, form_value in request_data.items()
                           if form_key.startswith('item_') and form_value != '']
    items = [scraper.scrape_item(item_slot, item_id) for item_slot, item_id in item_slot_id_tuples]

    return items


def _fetch_socket_stats(request_data):
    stats = defaultdict(int)
    meta_socket_active = False
    for form_key, form_value in request_data.items():
        if form_key.startswith('sockets_'):
            stats[form_key.replace('sockets_', '')] = int(form_value)
        elif form_key == 'meta_socket_active':
            assert isinstance(form_value, bool)
            meta_socket_active = form_value

    return stats, meta_socket_active
