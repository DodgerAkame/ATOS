import discord, random, logging, os, json, re, challonge, dateutil.parser, datetime, asyncio, yaml
from apscheduler.schedulers.asyncio import AsyncIOScheduler

with open('data/config.yml', 'r+') as f: config = yaml.safe_load(f)

if config["debug"] == True: logging.basicConfig(level=logging.DEBUG)

#### Version
version                             = "3.12"

### File paths
tournoi_path                        = config["paths"]["tournoi"]
participants_path                   = config["paths"]["participants"]
stream_path                         = config["paths"]["stream"]

#### Discord IDs
guild_id                            = config["discord"]["guild"]

### Server channels
blabla_channel_id                   = config["discord"]["channels"]["blabla"]
annonce_channel_id                  = config["discord"]["channels"]["annonce"]
check_in_channel_id                 = config["discord"]["channels"]["check_in"]
inscriptions_channel_id             = config["discord"]["channels"]["inscriptions"]
scores_channel_id                   = config["discord"]["channels"]["scores"]
stream_channel_id                   = config["discord"]["channels"]["stream"]
queue_channel_id                    = config["discord"]["channels"]["queue"]
flip_channel_id                     = config["discord"]["channels"]["flip"]
tournoi_channel_id                  = config["discord"]["channels"]["tournoi"]

### Info, non-interactive channels
ruleset_channel_id                  = config["discord"]["channels"]["ruleset"]
deroulement_channel_id              = config["discord"]["channels"]["deroulement"]
faq_channel_id                      = config["discord"]["channels"]["faq"]
resolution_channel_id               = config["discord"]["channels"]["resolution"]

### Server categories
tournoi_cat_id                      = config["discord"]["categories"]["tournoi"]
arenes_cat_id                       = config["discord"]["categories"]["arenes"]
arenes                              = discord.Object(id=arenes_cat_id)

### Role IDs
challenger_id                       = config["discord"]["roles"]["challenger"]
to_id                               = config["discord"]["roles"]["to"]

### Custom emojis
server_logo                         = config["discord"]["emojis"]["logo"]

#### Challonge
challonge_user                      = config["challonge"]["user"]

### Tokens
bot_secret                          = config["discord"]["secret"]
challonge_api_key                   = config["challonge"]["api_key"]

### Texts
welcome_text=f"""
Je t'invite à consulter le channel <#{deroulement_channel_id}> et <#{ruleset_channel_id}, et également <#{inscriptions_channel_id}> si tu souhaites t'inscrire à un tournoi. N'oublie pas de consulter les <#{annonce_channel_id}> régulièrement, et de poser tes questions aux TOs sur <#{faq_channel_id}>. Enfin, amuse-toi bien.
"""

help_text=f"""
:cd: **Commandes user :**
- `!help` : c'est la commande que tu viens de rentrer.
- `!bracket` : obtenir le lien du bracket en cours.

:video_game: **Commandes joueur :**
- `!dq` : se retirer du tournoi avant/après (DQ) que celui-ci ait commencé.
- `!flip` : pile/face, fonctionne uniquement dans <#{flip_channel_id}>.
- `!win` : rentrer le score d'un set dans <#{scores_channel_id}> *(paramètre : score)*.

:no_entry_sign: **Commandes administrateur :**
- `!purge` : purifier les channels relatifs à un tournoi.
- `!setup` : initialiser un tournoi *(paramètre : lien challonge valide)*.
- `!rm` : désinscrire/retirer (DQ) quelqu'un du tournoi *(paramètre : @mention | liste)*.
- `!add` : ajouter quelqu'un au tournoi *(paramètre : @mention | liste)*.

:tv: **Commandes stream :**
- `!stream` : obtenir toutes les informations relatives au stream (IDs, on stream, queue).
- `!setstream` : mettre en place l'arène de stream *(2 paramètres : ID MDP)*.
- `!addstream` : ajouter un set à la stream queue *(paramètre : n° | liste de n°)*.
- `!rmstream` : retirer un set de la stream queue *(paramètre : n° | queue | now)*.

*Version {version}, made by Wonderfall with :heart:*
"""

### Init things
bot = discord.Client()
challonge.set_credentials(challonge_user, challonge_api_key)
scheduler = AsyncIOScheduler()


### De-serialize & re-serialize datetime objects for JSON storage
def dateconverter(o):
    if isinstance(o, datetime.datetime):
        return o.__str__()

def dateparser(dct):
    for k, v in dct.items():
        try:
            dct[k] = datetime.datetime.strptime(v, "%Y-%m-%d %H:%M:%S")
        except:
            pass
    return dct

### Get int keys !
def int_keys(ordered_pairs):
    result = {}
    for key, value in ordered_pairs:
        try:
            key = int(key)
        except ValueError:
            pass
        result[key] = value
    return result


#### Notifier de l'initialisation
@bot.event
async def on_ready():
    print(f"-------------------------------------")
    print(f"           A.T.O.S. {version}        ")
    print(f"        Automated TO for Smash       ")
    print(f"                                     ")
    print(f"Logged on Discord as...              ")
    print(f"User : {bot.user.name}               ")
    print(f"ID   : {bot.user.id}                 ")
    print(f"-------------------------------------")
    await bot.change_presence(activity=discord.Game(version))
    await reload_tournament()


### A chaque arrivée de membre
@bot.event
async def on_member_join(member):
    await bot.get_channel(blabla_channel_id).send(f"{server_logo} Bienvenue à toi sur le serveur {member.guild.name}, <@{member.id}>. {welcome_text}")


### Récupérer informations du tournoi et initialiser tournoi.json
@bot.event
async def get_tournament(url):

    if re.compile("^(https?\:\/\/)?(challonge.com)\/.+$").match(url):
        try:
            bracket = challonge.tournaments.show(url.replace("https://challonge.com/", ""))
        except:
            return
    else:
        return

    tournoi = {
        "name": bracket["name"],
        "url": url,
        "id": bracket["id"],
        "limite": bracket["signup_cap"],
        "statut": bracket["state"],
        "début_tournoi": dateutil.parser.parse(str(bracket["start_at"])).replace(tzinfo=None),
        "début_check-in": dateutil.parser.parse(str(bracket["start_at"])).replace(tzinfo=None) - datetime.timedelta(hours = 1),
        "fin_check-in": dateutil.parser.parse(str(bracket["start_at"])).replace(tzinfo=None) - datetime.timedelta(minutes = 10),
        "on_stream": None,
        "stream": ["N/A", "N/A"]
    }

    return tournoi


### Ajouter un tournoi
@bot.event
async def setup_tournament(message):

    url = message.content.replace("!setup ", "")
    tournoi = await get_tournament(url)

    if tournoi == None:
        await message.add_reaction("⚠️")
        return

    elif datetime.datetime.now() > tournoi["début_tournoi"]:
        await message.add_reaction("🕐")
        return

    with open(tournoi_path, 'w') as f: json.dump(tournoi, f, indent=4, default=dateconverter)
    with open(participants_path, 'w') as f: json.dump({}, f, indent=4)
    with open(stream_path, 'w') as f: json.dump([], f, indent=4)

    await annonce_inscription()

    scheduler.add_job(start_check_in, id='start_check_in', run_date=tournoi["début_check-in"], replace_existing=True)
    scheduler.add_job(end_check_in, id='end_check_in', run_date=tournoi["fin_check-in"], replace_existing=True)
    scheduler.add_job(check_tournament_state, 'interval', id='check_tournament_state', minutes=1, replace_existing=True)

    await message.add_reaction("✅")
    await bot.change_presence(activity=discord.Game(f"{version} • {tournoi['name']}"))

    await purge_channels()


### S'execute à chaque lancement, permet de relancer les tâches en cas de crash
@bot.event
async def reload_tournament():

    try:
        with open(tournoi_path, 'r+') as f: tournoi = json.load(f, object_hook=dateparser)
        await bot.change_presence(activity=discord.Game(f"{version} • {tournoi['name']}"))

        # Relancer les tâches automatiques
        scheduler.add_job(start_check_in, id='start_check_in', run_date=tournoi["début_check-in"], replace_existing=True)
        scheduler.add_job(end_check_in, id='end_check_in', run_date=tournoi["fin_check-in"], replace_existing=True)
        scheduler.add_job(check_tournament_state, 'interval', id='check_tournament_state', minutes=1, replace_existing=True)

        print("Scheduled tasks for a tournament have been reloaded.")

        annonce = await bot.get_channel(inscriptions_channel_id).fetch_message(tournoi["annonce_id"])

        with open(participants_path, 'r+') as f: participants = json.load(f, object_pairs_hook=int_keys)

        # Avoir une liste des users ayant réagi
        for reaction in annonce.reactions:
            if str(reaction.emoji) == "✅":
                reactors = await reaction.users().flatten()
                break

        # Inscrire ceux qui ne sont pas dans les participants
        id_list = []

        for reactor in reactors:
            if reactor.id != bot.user.id:
                id_list.append(reactor.id)  # Récupérer une liste des IDs pour plus tard

                if reactor.id not in participants:
                    await inscrire(reactor)

        # Désinscrire ceux qui ne sont plus dans la liste des users ayant réagi
        for inscrit in participants:
            if inscrit not in id_list:
                await desinscrire(annonce.guild.get_member(inscrit))

        print("Missed inscriptions were also taken care of.")

    except:
        print("No scheduled tasks for any tournament had to be reloaded.")
        pass


### Annonce l'inscription
@bot.event
async def annonce_inscription():
    with open(tournoi_path, 'r+') as f: tournoi = json.load(f, object_hook=dateparser)

    annonce = (f"{server_logo} **{tournoi['name']}** \n"
               f":arrow_forward: **Date** : le {tournoi['début_tournoi'].strftime('%d.%m.%y à %Hh%M')} \n"
               f":arrow_forward: **Check-in** : de {tournoi['début_check-in'].strftime('%Hh%M')} à {tournoi['fin_check-in'].strftime('%Hh%M')} \n"
               f":arrow_forward: **Limite** : 0/{str(tournoi['limite'])} joueurs *(mise à jour en temps réel)* \n"
               f":arrow_forward: **Bracket** : {tournoi['url']} *(accessible en lecture)* \n"
               f":arrow_forward: **Format** : singles *(Super Smash Bros. Ultimate)*\n"
               "\n"
               "Merci de vous inscrire en ajoutant une réaction ✅ à ce message. Vous pouvez vous désinscrire en la retirant à tout moment. \n"
               "*Notez que votre pseudonyme Discord au moment de l'inscription sera celui utilisé dans le bracket.*")

    inscriptions_channel = bot.get_channel(inscriptions_channel_id)

    async for message in inscriptions_channel.history(): await message.delete()

    annonce_msg = await inscriptions_channel.send(annonce)
    tournoi['annonce_id'] = annonce_msg.id
    with open(tournoi_path, 'w') as f: json.dump(tournoi, f, indent=4, default=dateconverter)

    await annonce_msg.add_reaction("✅")
    await bot.get_channel(annonce_channel_id).send(f"{server_logo} Inscriptions pour le **{tournoi['name']}** ouvertes dans <#{inscriptions_channel_id}> ! Ce tournoi aura lieu le **{tournoi['début_tournoi'].strftime('%d.%m.%y à %Hh%M')}**.")


### Inscription
@bot.event
async def inscrire(member):

    try:
        with open(participants_path, 'r+') as f: participants = json.load(f, object_pairs_hook=int_keys)
        with open(tournoi_path, 'r+') as f: tournoi = json.load(f, object_hook=dateparser)

        if (datetime.datetime.now() > tournoi["fin_check-in"]) or (len(participants) >= tournoi['limite']):
            await bot.get_channel(inscriptions_channel_id).fetch_message(tournoi["annonce_id"]).remove_reaction("✅", member)
            return
    except:
        return

    if member.id not in participants:

        participants[member.id] = {
            "display_name" : member.display_name,
            "challonge" : challonge.participants.create(tournoi["id"], member.display_name)['id'],
            "checked_in" : False
        }

        if datetime.datetime.now() > tournoi["début_check-in"]:
            participants[member.id]["checked_in"] = True
            await member.add_roles(member.guild.get_role(challenger_id))

        with open(participants_path, 'w') as f: json.dump(participants, f, indent=4)
        await update_annonce()


### Désinscription
@bot.event
async def desinscrire(member):

    try:
        with open(participants_path, 'r+') as f: participants = json.load(f, object_pairs_hook=int_keys)
        with open(tournoi_path, 'r+') as f: tournoi = json.load(f, object_hook=dateparser)

        if datetime.datetime.now() > tournoi["fin_check-in"]: return
    except:
        return

    if member.id in participants:
        challonge.participants.destroy(tournoi["id"], participants[member.id]['challonge'])

        if datetime.datetime.now() > tournoi["début_check-in"]:
            await member.remove_roles(member.guild.get_role(challenger_id))

        del participants[member.id]
        with open(participants_path, 'w') as f: json.dump(participants, f, indent=4)
        await update_annonce()


### Mettre à jour l'annonce d'inscription
@bot.event
async def update_annonce():

    with open(participants_path, 'r+') as f: participants = json.load(f, object_pairs_hook=int_keys)
    with open(tournoi_path, 'r+') as f: tournoi = json.load(f, object_hook=dateparser)

    old_annonce = await bot.get_channel(inscriptions_channel_id).fetch_message(tournoi["annonce_id"])
    new_annonce = re.sub(r'[0-9]{1,2}\/', str(len(participants)) + '/', old_annonce.content)
    await old_annonce.edit(content=new_annonce)


### Début du check-in
@bot.event
async def start_check_in():

    guild = bot.get_guild(id=guild_id)
    with open(participants_path, 'r+') as f: participants = json.load(f, object_pairs_hook=int_keys)
    with open(tournoi_path, 'r+') as f: tournoi = json.load(f, object_hook=dateparser)

    for inscrit in participants:
        await guild.get_member(inscrit).add_roles(guild.get_role(challenger_id))

    scheduler.add_job(rappel_check_in, 'interval', id='rappel_check_in', minutes=10, replace_existing=True)

    await bot.get_channel(inscriptions_channel_id).send(f":information_source: Le check-in a commencé dans <#{check_in_channel_id}>. Vous pouvez toujours vous inscrire ici jusqu'à **{tournoi['fin_check-in'].strftime('%Hh%M')}** sans besoin de check-in par la suite, et tant qu'il y a de la place.")
    await bot.get_channel(check_in_channel_id).send(f"<@&{challenger_id}> Le check-in pour **{tournoi['name']}** a commencé : vous avez jusqu'à **{tournoi['fin_check-in'].strftime('%Hh%M')}** pour signaler votre présence, sinon vous serez retiré automatiquement du tournoi.\n- Utilisez `!in` pour confirmer votre inscription\n- Utilisez `!out` pour vous désinscrire")


### Rappel de check-in
@bot.event
async def rappel_check_in():

    with open(participants_path, 'r+') as f: participants = json.load(f, object_pairs_hook=int_keys)
    with open(tournoi_path, 'r+') as f: tournoi = json.load(f, object_hook=dateparser)

    rappel_msg = ""

    for inscrit in participants:
        if participants[inscrit]["checked_in"] == False:
            rappel_msg += f"- <@{inscrit}>\n"

    if rappel_msg != "":
        await bot.get_channel(check_in_channel_id).send(f":clock1: **Rappel de check-in !**\n{rappel_msg}\n\n*Vous avez jusqu'à {tournoi['fin_check-in'].strftime('%Hh%M')}, sinon vous serez désinscrit(s) automatiquement.*")


### Fin du check-in
@bot.event
async def end_check_in():

    guild = bot.get_guild(id=guild_id)
    with open(participants_path, 'r+') as f: participants = json.load(f, object_pairs_hook=int_keys)
    with open(tournoi_path, 'r+') as f: tournoi = json.load(f, object_hook=dateparser)

    try:
        scheduler.remove_job('rappel_check_in')
    except:
        pass

    for inscrit in participants:
        if participants[inscrit]["checked_in"] == False:
            challonge.participants.destroy(tournoi["id"], participants[inscrit]['challonge'])
            await guild.get_member(inscrit).remove_roles(guild.get_role(challenger_id))
            del participants[inscrit]

    with open(participants_path, 'w') as f: json.dump(participants, f, indent=4)
    await update_annonce()

    await bot.get_channel(check_in_channel_id).send(":clock1: **Le check-in est terminé.** Les personnes n'ayant pas check-in ont été retirées du bracket. Contactez les TOs s'il y a un quelconque problème, merci de votre compréhension.")
    await bot.get_channel(inscriptions_channel_id).send(":clock1: **Les inscriptions sont fermées.** Le tournoi débutera dans les minutes qui suivent : le bracket est en cours de finalisation. Contactez les TOs s'il y a un quelconque problème, merci de votre compréhension.")


### Prise en charge du check-in et check-out
@bot.event
async def check_in(message):

    with open(participants_path, 'r+') as f: participants = json.load(f, object_pairs_hook=int_keys)
    with open(tournoi_path, 'r+') as f: tournoi = json.load(f, object_hook=dateparser)

    if (message.author.id in participants) and (tournoi["fin_check-in"] > datetime.datetime.now() > tournoi["début_check-in"]):

        if message.content == "!in":
            participants[message.author.id]["checked_in"] = True
            await message.add_reaction("✅")

        elif message.content == "!out":
            challonge.participants.destroy(tournoi["id"], participants[message.author.id]['challonge'])
            await message.author.remove_roles(message.guild.get_role(challenger_id))
            del participants[message.author.id]
            await message.add_reaction("✅")

        else:
            return

        with open(participants_path, 'w') as f: json.dump(participants, f, indent=4)
        await update_annonce()


### Régulièrement executé
@bot.event
async def check_tournament_state():

    with open(participants_path, 'r+') as f: participants = json.load(f, object_pairs_hook=int_keys)
    with open(tournoi_path, 'r+') as f: tournoi = json.load(f, object_hook=dateparser)
    bracket = challonge.tournaments.show(tournoi["id"])

    ### Si le tournoi n'a pas encore commencé
    if (tournoi["statut"] == "pending") and (bracket['state'] != "pending"):
        await bot.get_channel(annonce_channel_id).send(f"{server_logo} Le tournoi **{tournoi['name']}** est officiellement lancé, voici le bracket : {tournoi['url']} *(vous pouvez y accéder à tout moment avec la commande `!bracket` sur Discord et Twitch)*")

        scorann = (f":information_source: La prise en charge des scores pour le tournoi **{tournoi['name']}** est automatisée :\n"
                   f":arrow_forward: Seul **le gagnant du set** envoie le score de son set, précédé par la **commande** `!win`.\n"
                   f":arrow_forward: Le message du score doit contenir le **format suivant** : `!win 2-0, 3-2, 3-1, ...`.\n"
                   f":arrow_forward: Consultez le bracket afin de **vérifier** les informations : {tournoi['url']}\n"
                   f":arrow_forward: En cas de mauvais score : contactez un TO pour une correction manuelle.")

        await bot.get_channel(scores_channel_id).send(scorann)

        queue_annonce = ":information_source: Le lancement des sets est automatisé. **Veuillez suivre les consignes de ce channel**, que ce soit par le bot ou les TOs. Notez que tout passage on stream sera notifié à l'avance, ici et/ou par DM."

        await bot.get_channel(queue_channel_id).send(queue_annonce)

        tournoi_annonce = (f"<@&{challenger_id}> *On arrête le freeplay !* Le tournoi est sur le point de commencer. Petit rappel :\n"
                           f"- Vos sets sont annoncés dès que disponibles dans <#{queue_channel_id}> : **ne lancez rien sans consulter ce channel**.\n"
                           f"- Le ruleset ainsi que les informations pour le bannissement des stages sont dispo dans <#{ruleset_channel_id}>.\n"
                           f"- Le gagnant d'un set doit rapporter le score **dès que possible** dans <#{scores_channel_id}> avec la commande `!win`.\n"
                           f"- Si vous le souhaitez vraiment, vous pouvez toujours DQ du tournoi avec la commande `!dq` à tout moment.\n"
                           f"- En cas de lag qui rend votre set injouable, n'hésitez pas à poster dans <#{resolution_channel_id}> où des TOs s'occuperont de vous.\n\n"
                           f"*L'équipe de TO et moi-même vous souhaitons un excellent tournoi.*")

        await bot.get_channel(tournoi_channel_id).send(tournoi_annonce)

        tournoi["statut"] = "underway"
        with open(tournoi_path, 'w') as f: json.dump(tournoi, f, indent=4, default=dateconverter)

    #### Si le tournoi est en cours
    elif bracket['state'] in ["in_progress", "underway"]:
        try:
            open_matches = challonge.matches.index(tournoi["id"], state="open")
            guild = bot.get_guild(id=guild_id)

            await launch_matches(open_matches, guild)
            await call_stream(open_matches, guild)
        except:
            pass

    ### Si le tournoi est terminé
    elif bracket['state'] in ["complete", "ended"]:
        guild = bot.get_guild(id=guild_id)
        await bot.get_channel(annonce_channel_id).send(f"{server_logo} Le tournoi **{tournoi['name']}** est terminé, merci à toutes et à tous d'avoir participé ! J'espère vous revoir bientôt.")
        for inscrit in participants: await guild.get_member(inscrit).remove_roles(guild.get_role(challenger_id))
        scheduler.remove_job('check_tournament_state')
        with open(participants_path, 'w') as f: json.dump({}, f, indent=4)
        with open(tournoi_path, 'w') as f: json.dump({}, f, indent=4)
        with open(stream_path, 'w') as f: json.dump([], f, indent=4)
        await bot.change_presence(activity=discord.Game(version))


### Nettoyer les channels liés aux tournois
@bot.event
async def purge_channels():
    guild = bot.get_guild(id=guild_id)

    for category, channels in guild.by_category():
        if (category != None) and (category.id == tournoi_cat_id):
            for channel in channels:
                async for message in channel.history():
                    await message.delete()
            break


### Affiche le bracket en cours
@bot.event
async def post_bracket(message):
    try:
        with open(tournoi_path, 'r+') as f: tournoi = json.load(f, object_hook=dateparser)
        await message.channel.send(f"{server_logo} **{tournoi['name']}** : {tournoi['url']}")
    except:
        await message.channel.send(":warning: Il n'y a pas de tournoi prévu à l'heure actuelle.")


### Pile/face basique
@bot.event
async def flipcoin(message):
    if message.content == "!flip":
        await message.channel.send(f"<@{message.author.id}> {random.choice(['Tu commences à faire les bans.', 'Ton adversaire commence à faire les bans.'])}")


### Ajout mannuel
@bot.event
async def add_inscrit(message):

    try:
        with open(participants_path, 'r+') as f: participants = json.load(f, object_pairs_hook=int_keys)
        with open(tournoi_path, 'r+') as f: tournoi = json.load(f, object_hook=dateparser)

        if (datetime.datetime.now() > tournoi["fin_check-in"]) or (len(participants) >= tournoi['limite']):
            await message.add_reaction("🚫")
            return

    except:
        await message.add_reaction("⚠️")
        return

    for member in message.mentions:

        if member.id not in participants:

            participants[member.id] = {
                "display_name" : member.display_name,
                "challonge" : challonge.participants.create(tournoi["id"], member.display_name)['id'],
                "checked_in" : False
            }

            if datetime.datetime.now() > tournoi["début_check-in"]:
                participants[member.id]["checked_in"] = True
                await member.add_roles(message.guild.get_role(challenger_id))

    with open(participants_path, 'w') as f: json.dump(participants, f, indent=4)
    await message.add_reaction("✅")


### Suppression/DQ manuel
@bot.event
async def remove_inscrit(message):

    with open(participants_path, 'r+') as f: participants = json.load(f, object_pairs_hook=int_keys)
    with open(tournoi_path, 'r+') as f: tournoi = json.load(f, object_hook=dateparser)

    for member in message.mentions:

        if member.id in participants:

            try:
                challonge.participants.destroy(tournoi["id"], participants[inscrit]['challonge'])
            except:
                await message.add_reaction("⚠️")
                return

            if datetime.datetime.now() > tournoi["début_check-in"]:
                await member.remove_roles(message.guild.get_role(challenger_id))

            if datetime.datetime.now() < tournoi["début_tournoi"]:
                del participants[inscrit]
                with open(participants_path, 'w') as f: json.dump(participants, f, indent=4)
                await update_annonce()

    await message.add_reaction("✅")


### Se DQ soi-même
@bot.event
async def self_dq(message):

    with open(participants_path, 'r+') as f: participants = json.load(f, object_pairs_hook=int_keys)
    with open(tournoi_path, 'r+') as f: tournoi = json.load(f, object_hook=dateparser)

    if message.author.id in participants:

        challonge.participants.destroy(tournoi["id"], participants[message.author.id]['challonge'])

        if datetime.datetime.now() > tournoi["début_check-in"]:
            await message.author.remove_roles(message.guild.get_role(challenger_id))

        if datetime.datetime.now() < tournoi["début_tournoi"]:
            del participants[message.author.id]
            with open(participants_path, 'w') as f: json.dump(participants, f, indent=4)
            await update_annonce()

        await message.add_reaction("✅")

    else:
        await message.add_reaction("⚠️")


### Gestion des scores
@bot.event
async def score_match(message):

    try:
        with open(participants_path, 'r+') as f: participants = json.load(f, object_pairs_hook=int_keys)
        with open(tournoi_path, 'r+') as f: tournoi = json.load(f, object_hook=dateparser)
        with open(stream_path, 'r+') as f: stream = json.load(f)

        if datetime.datetime.now() < tournoi["début_tournoi"]: return

        winner = participants[message.author.id]["challonge"] # Le gagnat est celui qui poste !
        match = challonge.matches.index(tournoi['id'], state="open", participant_id=winner)

        if match == []: return

    except:
        await message.add_reaction("⚠️")
        return
    
    try:
        score = re.search(r'([0-9]+) *\- *([0-9]+)', message.content).group().replace(" ", "")
        if score[0] < score[2]: score = score[::-1] # S'assurer que le premier chiffre est celui du gagnant
        if winner == match[0]["player2_id"]: score = score[::-1] # Inverser les chiffres pour que player1 soit le premier

    except:
        await message.channel.send(f"⚠️ <@{message.author.id}> Tu n'as pas employé le bon format de score *(3-0, 2-1, 3-2...)*, merci de le rentrer à nouveau.")
        return

    try:
        challonge.matches.update(tournoi['id'], match[0]["id"], scores_csv=score, winner_id=winner)

        if match[0]["suggested_play_order"] == tournoi["on_stream"]:
            tournoi["on_stream"] = None
            with open(tournoi_path, 'w') as f: json.dump(tournoi, f, indent=4, default=dateconverter)

        try:
            await discord.utils.get(message.guild.text_channels, name=str(match["suggested_play_order"])).delete()
        except:
            pass

        await message.add_reaction("✅")

    except:
        await message.add_reaction("⚠️")


### Lancer matchs ouverts
@bot.event
async def launch_matches(bracket, guild):

    with open(stream_path, 'r+') as f: stream = json.load(f)
    with open(participants_path, 'r+') as f: participants = json.load(f, object_pairs_hook=int_keys)
    with open(tournoi_path, 'r+') as f: tournoi = json.load(f, object_hook=dateparser)

    sets = ""

    for match in bracket:

        if match["underway_at"] == None:

            challonge.matches.mark_as_underway(tournoi["id"], match["id"])

            for joueur in participants:
                if participants[joueur]["challonge"] == match["player1_id"]: player1 = guild.get_member(joueur)
                if participants[joueur]["challonge"] == match["player2_id"]: player2 = guild.get_member(joueur)

            # Création d'un channel volatile pour le set
            try:
                gaming_channel = await guild.create_text_channel(
                    str(match["suggested_play_order"]),
                    overwrites = {
                        guild.default_role: discord.PermissionOverwrite(read_messages=False),
                        player1: discord.PermissionOverwrite(read_messages=True),
                        player2: discord.PermissionOverwrite(read_messages=True)
                    },
                    category=arenes)

            except:
                gaming_channel_txt = f":video_game: Je n'ai pas pu créer de channel, faites votre set en MP ou dans <#{tournoi_channel_id}>."

                if match["suggested_play_order"] in stream:
                    await player1.send(f"Tu joueras on stream pour ton prochain set contre **{player2.display_name}** : je te communiquerai les codes d'accès de l'arène quand ce sera ton tour.")
                    await player2.send(f"Tu joueras on stream pour ton prochain set contre **{player1.display_name}** : je te communiquerai les codes d'accès de l'arène quand ce sera ton tour.")

            else:
                gaming_channel_txt = f":video_game: Allez faire votre set dans le channel <#{gaming_channel.id}> !"

                gaming_channel_annonce = (f":arrow_forward: Ce channel a été créé pour le set suivant : <@{player1.id}> vs <@{player2.id}>\n"
                                          f"- Les règles du set doivent suivre celles énoncées dans <#{ruleset_channel_id}> (doit être lu au préalable).\n"
                                          f"- En cas de lag qui rend la partie injouable, utilisez le channel <#{resolution_channel_id}>.\n"
                                          f"- **Dès que le set est terminé**, le gagnant envoie le score dans <#{scores_channel_id}> avec la commande `!win`.\n\n"
                                          f":game_die: **{random.choice([player1.display_name, player2.display_name])}** est tiré au sort pour commencer le ban des stages.\n\n")

                if match["suggested_play_order"] in stream:
                    gaming_channel_annonce += f":tv: Vous jouerez **on stream**. Dès que ce sera votre tour, je vous communiquerai les codes d'accès de l'arène."

                await gaming_channel.send(gaming_channel_annonce)

            on_stream = "(prévu **on stream**) :tv:" if match["suggested_play_order"] in stream else ""
            sets += f":arrow_forward: À lancer : <@{player1.id}> vs <@{player2.id}> {on_stream}\n{gaming_channel_txt}\n\n"

    if sets != "": await bot.get_channel(queue_channel_id).send(sets)


### Ajout ID et MDP d'arène de stream
@bot.event
async def setup_stream(message):

    with open(tournoi_path, 'r+') as f: tournoi = json.load(f, object_hook=dateparser)
    arene = message.content.replace("!setstream ", "").split()

    if len(arene) == 2:
        tournoi["stream"] = arene
        with open(tournoi_path, 'w') as f: json.dump(tournoi, f, indent=4, default=dateconverter)
        await message.add_reaction("✅")

    else:
        await message.add_reaction("⚠️")


### Ajouter un set dans la stream queue
@bot.event
async def add_stream(message):

    with open(stream_path, 'r+') as f: stream = json.load(f)
    with open(tournoi_path, 'r+') as f: tournoi = json.load(f, object_hook=dateparser)

    try:
        to_add = list(map(int, message.content.replace("!addstream ", "").split()))
        bracket = challonge.matches.index(tournoi['id'], state=("open", "pending"))

    except:
        await message.add_reaction("⚠️")
        return

    for order in to_add:
        for match in bracket:
            if (match["suggested_play_order"] == order) and (match["underway_at"] == None) and (order not in stream):
                stream.append(order)
                break

    with open(stream_path, 'w') as f: json.dump(stream, f, indent=4)
    await message.add_reaction("✅")


### Enlever un set de la stream quee
@bot.event
async def remove_stream(message):

    if message.content == "!rmstream queue": # Reset la streamqueue
        with open(stream_path, 'w') as f: json.dump([], f, indent=4)
        await message.add_reaction("✅")

    elif message.content == "!rmstream now": # Reset le set on stream
        with open(tournoi_path, 'r+') as f: tournoi = json.load(f, object_hook=dateparser)
        tournoi["on_stream"] = None
        with open(tournoi_path, 'w') as f: json.dump(tournoi, f, indent=4, default=dateconverter)
        await message.add_reaction("✅")

    else:
        try:
            for order in list(map(int, message.content.replace("!rmstream ", "").split())): stream.remove(order)
            with open(stream_path, 'w') as f: json.dump(stream, f, indent=4)
            await message.add_reaction("✅")
        except:
            await message.add_reaction("⚠️")


### Infos stream
@bot.event
async def list_stream(message):

    try:
        with open(stream_path, 'r+') as f: stream = json.load(f)
        with open(participants_path, 'r+') as f: participants = json.load(f, object_pairs_hook=int_keys)
        with open(tournoi_path, 'r+') as f: tournoi = json.load(f, object_hook=dateparser)
        bracket = challonge.matches.index(tournoi['id'], state=("open", "pending"))
    except:
        await message.add_reaction("⚠️")
        return

    msg = f":information_source: Arène de stream :\n- **ID** : `{tournoi['stream'][0]}`\n- **MDP** : `{tournoi['stream'][1]}`\n"

    if tournoi["on_stream"] != None:

        for match in bracket:

            if tournoi["on_stream"] == match["suggested_play_order"]:

                for joueur in participants:
                    if participants[joueur]["challonge"] == match["player1_id"]: player1 = participants[joueur]['display_name']
                    if participants[joueur]["challonge"] == match["player2_id"]: player2 = participants[joueur]['display_name']

                msg += f":arrow_forward: **Set on stream actuel** *({tournoi['on_stream']})* : **{player1}** vs **{player2}**\n"
                break

        else: msg += ":warning: Huh ? Le set on stream ne semble pas/plus être en cours. Je suggère `!rmstream now`.\n"

    else:
        msg += ":stop_button: Il n'y a aucun set on stream à l'heure actuelle.\n"

    list_stream = ""

    for order in stream:

        for match in bracket:

            if match["suggested_play_order"] == order:

                for joueur in participants:
                    if participants[joueur]["challonge"] == match["player1_id"]:
                        player1 = participants[joueur]['display_name']
                        break
                else:
                    player1 = "(?)"

                for joueur in participants:
                    if participants[joueur]["challonge"] == match["player2_id"]:
                        player2 = participants[joueur]['display_name']
                        break
                else:
                    player2 = "(?)"

                list_stream += f"**{match['suggested_play_order']}** : *{player1}* vs *{player2}*\n"
                break

    if list_stream != "":
        msg += f":play_pause: Liste des sets prévus pour passer on stream prochainement :\n{list_stream}"
    else:
        msg += ":play_pause: Il n'y a aucun set prévu pour passer on stream prochainement."

    await message.channel.send(msg)


### Appeler les joueurs on stream
@bot.event
async def call_stream(bracket, guild):

    with open(stream_path, 'r+') as f: stream = json.load(f)
    with open(participants_path, 'r+') as f: participants = json.load(f, object_pairs_hook=int_keys)
    with open(tournoi_path, 'r+') as f: tournoi = json.load(f, object_hook=dateparser)

    if stream == [] or tournoi["on_stream"] != None: return

    for match in bracket:

        if (match["suggested_play_order"] == stream[0]) and (match["underway_at"] != None):

            for joueur in participants:
                if participants[joueur]["challonge"] == match["player1_id"]: player1 = guild.get_member(joueur)
                if participants[joueur]["challonge"] == match["player2_id"]: player2 = guild.get_member(joueur)

            gaming_channel = discord.utils.get(guild.text_channels, name=str(match["suggested_play_order"]))

            if gaming_channel == None:
                await player1.send(f"C'est ton tour de passer on stream ! N'oublie pas de donner les scores dès que le set est fini. Voici les codes d'accès de l'arène :\n:arrow_forward: **ID** : `{tournoi['stream'][0]}`\n:arrow_forward: **MDP** : `{tournoi['stream'][1]}`")
                await player2.send(f"C'est ton tour de passer on stream ! N'oublie pas de donner les scores dès que le set est fini. Voici les codes d'accès de l'arène :\n:arrow_forward: **ID** : `{tournoi['stream'][0]}`\n:arrow_forward: **MDP** : `{tournoi['stream'][1]}`")
            else:
                await gaming_channel.send(f":clapper: C'est votre tour de passer on stream ! **N'oubliez pas de donner les scores dès que le set est fini.** Voici les codes d'accès de l'arène :\n:arrow_forward: **ID** : `{tournoi['stream'][0]}`\n:arrow_forward: **MDP** : `{tournoi['stream'][1]}`")

            await bot.get_channel(stream_channel_id).send(f":arrow_forward: Envoi on stream du set n°{match['suggested_play_order']} : **{player1.display_name}** vs **{player2.display_name}** !")

            tournoi["on_stream"] = match["suggested_play_order"]
            with open(tournoi_path, 'w') as f: json.dump(tournoi, f, indent=4, default=dateconverter)

            stream.remove(match["suggested_play_order"])
            with open(stream_path, 'w') as f: json.dump(stream, f, indent=4)

            break


### Si administrateur
@bot.event
async def author_is_admin(message):

    if to_id in [y.id for y in message.author.roles]:
        return True

    else:
        await message.add_reaction("🚫")
        return False


### À chaque ajout de réaction
@bot.event
async def on_raw_reaction_add(event):
    if event.user_id == bot.user.id: return

    if (event.emoji.name == "✅") and (event.channel_id == inscriptions_channel_id):

        with open(tournoi_path, 'r+') as f: tournoi = json.load(f, object_hook=dateparser)

        if event.message_id == tournoi["annonce_id"]:
            await inscrire(event.member) # available for REACTION_ADD only


### À chaque suppression de réaction
@bot.event
async def on_raw_reaction_remove(event):
    if event.user_id == bot.user.id: return

    if (event.emoji.name == "✅") and (event.channel_id == inscriptions_channel_id):

        with open(tournoi_path, 'r+') as f: tournoi = json.load(f, object_hook=dateparser)

        if event.message_id == tournoi["annonce_id"]:
            await desinscrire(bot.get_guild(id=guild_id).get_member(event.user_id)) # event.member not available for REACTION_REMOVE


### À chaque message
@bot.event
async def on_message(message):

    if message.author.id == bot.user.id: return

    elif message.channel.id == check_in_channel_id: await check_in(message)

    elif message.channel.id == flip_channel_id: await flipcoin(message)

    elif (message.channel.id == scores_channel_id) and (message.content.startswith("!win ")): await score_match(message)

    elif message.content == '!bracket': await post_bracket(message)

    elif message.content == '!dq': await self_dq(message)

    elif message.content == '!help': await message.channel.send(help_text)

    elif ((message.content in ["!purge", "!stream"] or message.content.startswith(('!setup ', '!rm ', '!add ', '!setstream ', '!addstream ', '!rmstream ')))) and (await author_is_admin(message)):
        if message.content == '!purge': await purge_channels()
        elif message.content == '!stream': await list_stream(message)
        elif message.content.startswith('!setup '): await setup_tournament(message)
        elif message.content.startswith('!rm '): await remove_inscrit(message)
        elif message.content.startswith('!add '): await add_inscrit(message)
        elif message.content.startswith('!setstream '): await setup_stream(message)
        elif message.content.startswith('!addstream '): await add_stream(message)
        elif message.content.startswith('!rmstream '): await remove_stream(message)



#### Scheduler
scheduler.start()

#### Lancement du bot
bot.run(bot_secret)