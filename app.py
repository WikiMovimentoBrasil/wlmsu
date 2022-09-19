import yaml
import os
import json
import requests
from flask import Flask, render_template, request, redirect, session, url_for, jsonify, g, flash
from flask_babel import Babel, gettext
from oauth_wikidata import get_username, upload_file, get_token, build_text
from requests_oauthlib import OAuth1Session
from wikidata import query_monuments, query_monuments_without_coords, query_monument, get_category_info, get_article,\
    get_sitelinks, api_post_request, query_monuments_selected
import gspread
from oauth2client.service_account import ServiceAccountCredentials

__dir__ = os.path.dirname(__file__)
app = Flask(__name__)
app.config.update(yaml.safe_load(open(os.path.join(__dir__, 'config.yaml'))))

BABEL = Babel(app)


##############################################################
# LOGIN
##############################################################
@app.before_request
def init_profile():
    g.profiling = []


@app.before_request
def global_user():
    g.user = get_username()


@app.route('/login')
def login():
    next_page = request.args.get('next')
    if next_page:
        session['after_login'] = next_page

    client_key = app.config['CONSUMER_KEY']
    client_secret = app.config['CONSUMER_SECRET']
    base_url = 'https://meta.wikimedia.org/w/index.php'
    request_token_url = base_url + '?title=Special%3aOAuth%2finitiate'

    oauth = OAuth1Session(client_key,
                          client_secret=client_secret,
                          callback_uri='oob')
    fetch_response = oauth.fetch_request_token(request_token_url)

    session['owner_key'] = fetch_response.get('oauth_token')
    session['owner_secret'] = fetch_response.get('oauth_token_secret')

    base_authorization_url = 'https://meta.wikimedia.org/wiki/Special:OAuth/authorize'
    authorization_url = oauth.authorization_url(base_authorization_url,
                                                oauth_consumer_key=client_key)
    return redirect(authorization_url)


@app.route("/oauth-callback", methods=["GET"])
def oauth_callback():
    base_url = 'https://meta.wikimedia.org/w/index.php'
    client_key = app.config['CONSUMER_KEY']
    client_secret = app.config['CONSUMER_SECRET']

    oauth = OAuth1Session(client_key,
                          client_secret=client_secret,
                          resource_owner_key=session['owner_key'],
                          resource_owner_secret=session['owner_secret'])

    oauth_response = oauth.parse_authorization_response(request.url)
    verifier = oauth_response.get('oauth_verifier')
    access_token_url = base_url + '?title=Special%3aOAuth%2ftoken'
    oauth = OAuth1Session(client_key,
                          client_secret=client_secret,
                          resource_owner_key=session['owner_key'],
                          resource_owner_secret=session['owner_secret'],
                          verifier=verifier)

    oauth_tokens = oauth.fetch_access_token(access_token_url)
    session['owner_key'] = oauth_tokens.get('oauth_token')
    session['owner_secret'] = oauth_tokens.get('oauth_token_secret')
    next_page = session.get('after_login')

    return redirect(next_page)


##############################################################
# LOCALIZAÇÃO
##############################################################
# Função para pegar a língua de preferência do usuário
@BABEL.localeselector
def get_locale():
    if request.args.get('lang'):
        session['lang'] = request.args.get('lang')
    return session.get('lang', 'nl')


# Função para mudar a língua de exibição do conteúdo
@app.route('/set_locale')
def set_locale():
    next_page = request.args.get('return_to')
    lang = request.args.get('lang')

    session["lang"] = lang.replace("-", "_")
    redirected = redirect(next_page)
    redirected.delete_cookie('session', '/item')
    return redirected


@app.context_processor
def inject_language():
    possible_languages = {
        "aa": "afar",
        "ab": "Аҧсуа",
        "ae": "avesta",
        "af": "Afrikaans",
        "ak": "akana",
        "am": "አማርኛ",
        "an": "aragonés",
        "ar": "العربية",
        "as": "অসমীয়া",
        "av": "авар",
        "ay": "aymar",
        "az": "Azərbaycan",
        "ba": "Башҡорт",
        "be": "беларуская",
        "bg": "български",
        "bi": "Bislama",
        "bih": "भोजपुरी",
        "bm": "bamanankan",
        "bn": "বাংলা",
        "bo": "བོད་ཡིག",
        "br": "brezhoneg",
        "bs": "bosanski",
        "ca": "català",
        "ce": "нохчийн",
        "ch": "chamoru",
        "co": "corsu",
        "cr": "ᓀᐦᐃᔭᐤ",
        "cs": "česky",
        "cu": "ѩзыкъ словѣньскъ",
        "cv": "Чӑваш",
        "cy": "Cymraeg",
        "da": "dansk",
        "de": "Deutsch",
        "dv": "ދިވެހިބަސް",
        "dz": "ཇོང་ཁ",
        "ee": "Ɛʋɛ",
        "el": "Ελληνικά",
        "en": "English",
        "eo": "Esperanto",
        "es": "español",
        "et": "eesti",
        "eu": "euskara",
        "fa": "فارسی",
        "ff": "Fulfulde",
        "fi": "suomi",
        "fj": "na vosa Vakaviti",
        "fo": "føroyskt",
        "fr": "Français",
        "fy": "Frysk",
        "ga": "Gaeilge",
        "gd": "Gàidhlig",
        "gl": "galego",
        "gn": "Avañe'ẽ",
        "gu": "ગુજરાતી",
        "gv": "Gaelg",
        "ha": "حَوْسََ",
        "he": "עִבְרִית",
        "hi": "हिन्दी",
        "ho": "Hiri Motu",
        "hr": "hrvatski",
        "ht": "kreyòl ayisyen",
        "hu": "magyar",
        "hy": "Հայերեն",
        "hz": "Otjiherero",
        "ia": "Interlingua",
        "id": "bahasa Indonesia",
        "ie": "Interlingue",
        "ig": "Ibo",
        "ii": "ꆇꉙ",
        "ik": "Iñupiaq",
        "io": "Ido",
        "is": "íslenska",
        "it": "italiano",
        "iu": "ᐃᓄᒃᑎᑐᑦ",
        "ja": "日本語",
        "jv": "Basa Jawa",
        "ka": "ქართული",
        "kg": "Kikongo",
        "ki": "Gĩkũyũ",
        "kj": "kuanyama",
        "kk": "қазақша",
        "kl": "kalaallisut",
        "km": "ភាសាខ្មែរ",
        "kn": "ಕನ್ನಡ",
        "ko": "한국어",
        "kr": "kanuri",
        "ks": "कश्मीरी - (كشميري)",
        "ku": "كوردي",
        "kv": "коми",
        "kw": "Kernewek",
        "ky": "Кыргызча",
        "la": "latine",
        "lb": "Lëtzebuergesch",
        "lg": "Luganda",
        "li": "Lèmburgs",
        "ln": "Lingala",
        "lo": "ລາວ",
        "lt": "lietuvių",
        "lu": " ",
        "lv": "latviešu",
        "mai": "मैथिली",
        "mg": "Malagasy fiteny",
        "mh": "Kajin M̧ajeļ; Ebon",
        "mi": "te reo Māori",
        "mk": "македонски",
        "ml": "മലയാളം",
        "mn": "монгол",
        "mr": "मराठी",
        "ms": "بهاس ملاي",
        "mt": "bil-Malta",
        "my": "မန္မာစာ",
        "na": "ekakairũ naoero",
        "nb": "Bokmål",
        "nd": "isiNdebele",
        "ne": "नेपाली",
        "ng": "O(shi)wambo",
        "nl": "Nederlands",
        "nn": "Norsk Nynorsk",
        "no": "norsk",
        "nr": "Ndébélé",
        "nv": "Diné bizaad",
        "ny": "chiCheŵa",
        "oc": "occitan",
        "oj": "ᐊᓂᔑᓇᐯ",
        "om": "Oromoo",
        "or": "ଓଡ଼ିଆ",
        "os": "иронау",
        "pa": "ਪੰਜਾਬੀ",
        "pi": "पािऴ",
        "pl": "polski",
        "ps": "پښتو",
        "pt": "português",
        "pt_br": "português brasileiro",
        "qu": "Runa Simi",
        "rm": "rumantsch",
        "rn": "kiRundi",
        "ro": "română",
        "ru": "русский",
        "rw": "kinyaRwanda",
        "sa": "संस्कृत",
        "sc": "sardu",
        "sd": "सिनधि",
        "se": "sámegiella",
        "sg": "sängö",
        "sh": "хрватскосрпск",
        "si": "සිංහල",
        "sk": "slovenčina",
        "sl": "slovenščina",
        "sm": "Gagana Samoa",
        "sn": "chiShona",
        "so": "Soomaaliga",
        "sq": "Shqip",
        "sr": "српски",
        "ss": "SiSwati",
        "st": "seSotho",
        "su": "basa Sunda",
        "sv": "svenska",
        "sw": "Kiswahili",
        "ta": "தமிழ்",
        "te": "తెలుగు",
        "tg": "Тоҷикӣ",
        "th": "ภาษาไทย",
        "ti": "ትግርኛ",
        "tk": "Түркмен",
        "tl": "Tagalog",
        "tn": "seTswana",
        "to": "faka-Tonga",
        "tr": "Türkçe",
        "ts": "xiTsonga",
        "tt": "Tatarça",
        "tw": "Twi",
        "ty": "reo Tahiti",
        "ug": "Уйғурче",
        "uk": "українська",
        "ur": "اردو",
        "uz": "Ўзбек",
        "ve": "tshiVenḓa",
        "vi": "tiếng Việt",
        "vo": "Volapük",
        "wa": "walon",
        "wo": "Wolof",
        "xh": "isiXhosa",
        "yi": "ייִדיש",
        "yo": "Yorùbá",
        "za": "Saɯ cueŋƅ",
        "zh": "漢語; 汉语; 中文",
        "zu": "isiZulu",
    }
    translations_folders = os.listdir(os.path.join(__dir__, "translations"))
    return dict(AVAILABLE_LANGUAGES={x: possible_languages[x].capitalize() if x in possible_languages else x for x in translations_folders},
                CURRENT_LANGUAGE=session.get('lang', request.accept_languages.best_match(app.config['LANGUAGES'])))

##############################################################
# PÁGINAS
##############################################################
# Página de erro
@app.errorhandler(400)
@app.errorhandler(401)
@app.errorhandler(403)
@app.errorhandler(404)
@app.errorhandler(405)
@app.errorhandler(406)
@app.errorhandler(408)
@app.errorhandler(409)
@app.errorhandler(410)
@app.errorhandler(411)
@app.errorhandler(412)
@app.errorhandler(413)
@app.errorhandler(414)
@app.errorhandler(415)
@app.errorhandler(416)
@app.errorhandler(417)
@app.errorhandler(418)
@app.errorhandler(422)
@app.errorhandler(423)
@app.errorhandler(424)
@app.errorhandler(429)
@app.errorhandler(500)
@app.errorhandler(501)
@app.errorhandler(502)
@app.errorhandler(503)
@app.errorhandler(504)
@app.errorhandler(505)
def page_not_found(e):
    username = get_username()
    lang = get_locale()
    return render_template('error.html',
                           username=username,
                           lang=lang,
                           error=e.original_exception.args[0])


# Função para exibir a tela de descrição do aplicativo
@app.route('/about')
@app.route('/sobre')
def about():
    username = get_username()
    lang = get_locale()
    return render_template('sobre.html',
                           username=username,
                           lang=lang)


# Página inicial
@app.route('/')
@app.route('/home')
@app.route('/inicio')
@app.route('/mapa')
@app.route('/map')
def mapa():
    username = get_username()
    lang = get_locale()
    return render_template("map.html",
                           username=username,
                           lang=lang)


@app.route('/mapa/<uf>')
@app.route('/map/<uf>')
def mapa_uf(uf):
    username = get_username()
    lang = get_locale()
    states_qids = {"br": "Q847680", "cm": "Q952510", "cr": "Q1130141", "ma": "Q1140897", "ni": "Q1147515",
                   "pr": "Q1140891", "pm": "Q1130134", "sa": "Q1351157", "si": "Q1130138", "wa": "Q1147524"}

    monuments = query_monuments(states_qids[uf.lower()], lang)
    qids_with_image = []
    qids_without_image = []
    comandos = "var "

    for item in monuments:
        tooltip = item["label"]
        tooltip_style = "{direction:'top', offset: [0, -37]}"
        popup = "<span style='text-align:center'><b>" + item["label"] + "</b></span><br><br>" + "<a class='custom-link' target='_self' href='" + url_for("monumento", qid=item['item']) + "'><button class='send_button'><i class='fa-solid fa-arrow-up-from-bracket'></i> " + gettext("Ver mais informações e enviar fotografias") + "</div>"
        popup_style = "{closeButton: false}"
        if "imagem" in item and item["imagem"] != "No-image.png":
            if "types" in item and item["types"]:
                comandos += item["item"] + " = L.marker({lon: " + item["coord"][0] + ", lat: " + item["coord"][1] + "}, {icon: greenIcon})" + ".bindTooltip(\"" + tooltip + "\", " + tooltip_style + ").bindPopup(\"" + popup + "\", " + popup_style + ").on('click', markerOnClick)" + "".join(item["types"]) + ",\n"
            qids_with_image.append(item["item"])
        else:
            comandos += item["item"] + " = L.marker({lon: " + item["coord"][0] + ", lat: " + item["coord"][1] + "}, {icon: redIcon})" + ".bindTooltip(\"" + tooltip + "\", " + tooltip_style + ").bindPopup(\"" + popup + "\", " + popup_style + ").on('click', markerOnClick).addTo(markers_without_image),\n"
            qids_without_image.append(item["item"])

        comandos = comandos[:-2] + ";\n"

    return render_template("map_uf.html",
                           markers=comandos,
                           markers_list="[" + ",".join(list(set(qids_without_image+qids_with_image))) + "]",
                           bounds=uf_bounds(uf),
                           username=username,
                           lang=lang,
                           uf=uf)


@app.route('/mapa/<uf>/geolocalizar')
@app.route('/map/<uf>/geolocate')
def geolocate(uf):
    username = get_username()
    lang = get_locale()
    states_qids = {"br": "Q847680", "cm": "Q952510", "cr": "Q1130141", "ma": "Q1140897", "ni": "Q1147515",
                   "pr": "Q1140891", "pm": "Q1130134", "sa": "Q1351157", "si": "Q1130138", "wa": "Q1147524"}

    monuments, locais = query_monuments_without_coords(states_qids[uf.lower()], lang)

    return render_template("geolocate.html",
                           bounds=uf_bounds(uf),
                           monuments=monuments,
                           locais=locais,
                           username=username,
                           lang=lang,
                           uf=uf)


@app.route('/mapa/sugerir', methods=['GET', 'POST'])
@app.route('/map/suggest', methods=['GET', 'POST'])
def suggest():
    username = get_username()
    lang = get_locale()

    if request.method == "POST":
        scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
        creds = ServiceAccountCredentials.from_json_keyfile_name(os.path.join(__dir__, 'credentials.json'), scope)
        client = gspread.authorize(creds)
        spreadsheet = app.config["SUGGESTIONS_SPREADSHEET"]
        gsheet = client.open(spreadsheet).sheet1

        name = request.form.get("inputName") or ""
        state = request.form.get("inputState") or ""
        local = request.form.get("inputLocal") or ""
        address = request.form.get("inputAddress") or ""
        url = request.form.get("inputURL") or ""
        comments = request.form.get("inputComments") or ""

        gsheet.append_row([name, state, local, address, url, comments])
        flash(gettext(u'Sua sugestão para adicionar %(val)s à lista de monumentos foi enviada com sucesso!', val=name))

    uf = request.args["uf"] if "uf" in request.args else ""

    return render_template("suggest.html",
                           username=username,
                           lang=lang,
                           uf=uf)


@app.route('/monumento/<qid>', methods=['GET', 'POST'])
@app.route('/monument/<qid>', methods=['GET', 'POST'])
def monumento(qid):
    username = get_username()
    lang = get_locale()

    if request.method == "POST":
        return send_file()
    else:
        metadata = query_monument(qid, lang)
        if "commons_cat" in metadata and metadata["commons_cat"]:
            metadata["cat_info"] = get_category_info(metadata["commons_cat"][0])

        metadata["sitelinks"] = get_sitelinks(qid)
        aux_lang = "pt" if lang == "pt-br" else lang

        if aux_lang in metadata["sitelinks"]:
            metadata["article"] = get_article(aux_lang, metadata["sitelinks"][aux_lang])
            metadata["article_wiki"] = aux_lang
            metadata["article_name"] = metadata["sitelinks"][aux_lang]

        return render_template("item.html",
                               metadata=metadata,
                               username=username,
                               lang=lang)


##############################################################
# CONSULTAS E REQUISIÇÕES
##############################################################
@app.route('/postCoordinates', methods=['GET', 'POST'])
def post_coordinates():
    if request.method == "POST":
        jsondata = request.get_json()
        item = jsondata['item']
        lat = jsondata['lat']
        lon = jsondata['lon']
        username = get_username()
        token = get_token()

        params = {
            "action": "wbcreateclaim",
            "format": "json",
            "entity": item,
            "property": "P625",
            "snaktype": "value",
            "value": "{\"latitude\":" + str(lat) + ",\"longitude\":" + str(lon) + ",\"globe\":\"http://www.wikidata.org/entity/Q2\",\"precision\":0.000001}",
            "token": token,
        }

        result = api_post_request(params).json()

        message = gettext(r"Coordenadas inseridas com sucesso!") if result["success"] else gettext(r"Algo deu errado, atualize esta página e tente novamente. Caso o erro persista, entre em contato na seção \"Sobre\".")
        answer = {"qid": item, "message": message}
        return json.dumps(answer), 200


def uf_bounds(uf):
    bounds = {
        "br": [[3.9988538, -55.5004364], [5.3719097, -54.7209489]],
        "cm": [[5.4855246, -55.2276735], [6.195, -54.6217863]],
        "cr": [[5.3202138, -56.6130911], [6.173, -55.8808852]],
        "ma": [[5.2350227, -54.7492794], [6.1811395, -53.8601382]],
        "ni": [[5.2200867, -57.3413817], [6.225, -56.455791]],
        "pr": [[4.9845773, -56.0266243], [5.7013662, -54.6256835]],
        "pm": [[5.7665704, -55.2467751], [6.151, -55.0940889]],
        "sa": [[5.3938524, -56.0584504], [6.18, -55.2826454]],
        "si": [[1.8312802, -58.070833], [5.5316947, -53.9800408]],
        "wa": [[5.6552916, -55.3584959], [6.154, -55.0682509]]
    }
    return bounds[uf.lower()]


@app.route('/send_file', methods=["POST"])
def send_file():
    username = get_username()

    status_code = "ERROR"
    if request.method == "POST":
        uploaded_file = request.files.getlist('uploaded_file')[0]
        form = request.form

        # Enviar imagem
        if username:
            text = build_text(form)
            data = upload_file(uploaded_file, form, text)
            if "error" in data and data["error"]["code"] == "fileexists-shared-forbidden":
                message = gettext(u"Uma imagem com este exato título já existe. Por favor, reformule o título.")
            elif "upload" in data and "warnings" in data["upload"] and "duplicate" in data["upload"]["warnings"]:
                message = gettext(u"Esta imagem é uma duplicata exata da imagem https://commons.wikimedia.org/wiki/File:%(file_)s",
                    file_=data["upload"]["warnings"]["duplicate"][0])
            elif "upload" in data and "warnings" in data["upload"] and "duplicate-archive" in data["upload"]["warnings"]:
                message = gettext(u"Esta imagem é uma duplicata exata de uma outra imagem que foi deletada da base.")
            elif "upload" in data and "warnings" in data["upload"] and "was-deleted" in data["upload"]["warnings"]:
                message = gettext(u"Uma outra imagem costumava utilizar este mesmo título. Por favor, reformule o título.")
            elif "upload" in data and "warnings" in data["upload"] and "exists" in data["upload"]["warnings"]:
                message = gettext(u"Uma imagem com este exato título já existe. Por favor, reformule o título.")
            #TODO:lockmanager-fail-conflict is an error that does not impact in sending the files. For now, treat as success
            elif "error" in data and "code" in data["error"] and data["error"]["code"] == "lockmanager-fail-conflict":
                message = gettext(u"Imagem enviada com sucesso! Verifique suas contribuições clicando em seu nome de usuário(a).") + " (lockmanager-fail-conflict)"
                status_code = "SUCCESS"
            elif "error" in data:
                message = data["error"]["code"]
            elif "upload" in data and "result" in data["upload"] and data["upload"]["result"] == "Success":
                message = gettext(u"Imagem enviada com sucesso! Verifique suas contribuições clicando em seu nome de usuário(a).")
                status_code = "SUCCESS"
            else:
                message = gettext(u"Error.")
        else:
            message = gettext(u'Ocorreu algum erro! Verifique o formulário e tente novamente. Caso o erro persista, '
                              u'por favor, reporte em https://github.com/WikiMovimentoBrasil/wlmsu/issues')
        return jsonify({"message": message, "status": status_code, "filename": form["filename"]})


@app.route('/print_selection', methods=["POST"])
def print_selection():
    if request.method == "POST":
        jsondata = request.get_json()
        items = jsondata['items']
        results = query_monuments_selected(items, get_locale())
        return jsonify(results), 200


##############################################################
# MAIN
##############################################################
if __name__ == '__main__':
    app.run()
