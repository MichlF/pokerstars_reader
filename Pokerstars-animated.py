
# * Import modules
import gspread  # for manipulating google sheets https://gspread.readthedocs.io/en/latest/index.html
import math
import os
import string
import seaborn as sns
import numpy as np
import matplotlib.animation as animation
import matplotlib.pyplot as plt
import smtplib
import imghdr
import csv
from email.message import EmailMessage
from matplotlib import style
from oauth2client.service_account import ServiceAccountCredentials
from time import time
from pathlib import Path
# %matplotlib inline #  for jupyter notebook

# TODO: check for whether homegame, if homegame we wanna evauluate money
# TODO: add preflop raises
# TODO: add family pot percentage (counter)
# TODO: Clean up the code
# ? Possible to implement add rebuys of known players when they change accounts to buy in again

# * Functions


def create_dir(path):
    """Helper function to create directories

    Parameters
    ----------
    path : str
        folder path to create

    Returns
    -------
    path : str
        returns the path
    """
    try:
        os.makedirs(path)
    except OSError:
        print(f"{path} already exists. Moved on...")

    return path


def timer(func):
    """Decorater/Wrapper function to measure elapsed time of input function

    Parameters
    ----------
    func : function
        to be wrapped function
    """

    def f(*args, **kwargs):
        before = time()
        rv = func(*args, **kwargs)
        after = time()
        print("elapsed", after-before)
        return rv
    return f


def data_extract(rawlines):
    """Extracts relevant data from hand history file (.txt)

    Parameters
    ----------
    rawlines : list of lists
        Contains the content of hand history file as a list of lists

    Returns
    -------
    each_chips : dict
        For each player name (dict key) list of two lists for each hand played: chip count, corresponding hand number
    each_wins : dict
        For each player name (dict key) list of four lists of 0/1 for each hand played: won w/ showdown, lost w/ or w/o showdown, won w/o showdown, preflop fold
    count_hand : list of ints
        List of each hand number
    each_rake : list of ints
        List of values for rake per hand
    each_potsize : list of ints
        List of values for pot size per hand
    each_allin : dict
        For each player name (dict key) list of four lists of 0/1 for each hand played: all-in, all-in won, bust, rebuy
    count_family_pot : list of ints
        List of 0/1 indicating presence/absence of a family pot
    """

    each_chips, each_wins, count_hand, each_rake, each_potsize, count_allin, count_family_pot = [
        {}, {}, [0], [.01e-20], [.01e-20], {}, [0]]
    for line in rawlines:
        words = line.split()
        if len(words) > 4 and words[0] not in ['***', 'Board', 'Table']:
            # Hand count
            if words[-1] == "ET":
                count_hand.append(count_hand[-1]+1)
                count_family_pot.append(1)
            # Chip count
            elif words[-1] == "chips)":
                chips = int(words[-3][1:])
                if words[2] in each_chips.keys():
                    each_chips[words[2]][0].append(chips)
                    each_chips[words[2]][1].append(count_hand[-1])
                else:
                    each_chips[words[2]] = [
                        [chipCount_start, chips], [0, count_hand[-1]]]
                # Update all-ins
                if words[2] in count_allin.keys():
                    [item.append(0) for item in count_allin[words[2]]]
                    # Check if player went bust and rebought
                    if count_allin[words[2]][2][-2]:
                        count_allin[words[2]][3][-1] = 1
                else:
                    count_allin[words[2]] = [[0, 0], [0, 0], [0, 0], [0, 0]]
                # Update wins
                if words[2] in each_wins.keys():
                    [item.append(0) for item in each_wins[words[2]]]
                else:
                    each_wins[words[2]] = [[0, 0], [0, 0], [0, 0], [0, 0]]
            # All-In
            elif words[-1] == "all-in":
                words_stripped = words[0].translate(
                    {ord(i): None for i in ':'})  # strip the semicolon from the name
                count_allin[words_stripped][0][-1] = 1
            # Uncalled bet returns
            elif words[0] == "Uncalled":
                # If all-in bet is uncalled and remainder returned, status all-in has to be reset to 0
                if count_allin[words[5]][0][-1] == 1:
                    count_allin[words[5]][0][-1] = 0
            # Win w/ showdown count
            elif "won" in words:
                each_wins[words[2]][0][-1] = 1
                # if all-in and won
                if count_allin[words[2]][0][-1] == 1:
                    count_allin[words[2]][1][-1] = 1
            # Lost count
            elif "lost" in words or "mucked" in words:
                each_wins[words[2]][1][-1] = 1
                # if all-in and lost/mucked, player went bust
                if count_allin[words[2]][0][-1] == 1:
                    count_allin[words[2]][2][-1] = 1
            # Won w/o showdown count
            elif words[-2] == "collected":
                each_wins[words[2]][2][-1] = 1
                # if all-in and won
                if count_allin[words[2]][0][-1] == 1:
                    count_allin[words[2]][1][-1] = 1
            # Rake and pot size
            elif words[1] == "pot":
                # Rake
                if int(words[-1]) == 0:
                    each_rake.append(.01e-20)
                else:
                    each_rake.append(float(words[-1]))
                # Pot
                each_potsize.append(float(words[2]))
            # Preflop fold
            elif "before" in words:
                each_wins[words[2]][3][-1] = 1
                count_family_pot[-1] = 0

    return count_hand, each_chips, each_wins, each_rake, each_potsize, count_allin, count_family_pot


def data_get():
    """Function that opens the hand history file and calls data_extract function

    Returns
    -------
    list of lists
        contains all information returned by data_extract()
    """

    with open(filename) as raw_file:
        raw_content = raw_file.readlines()
        content = [x.strip() for x in raw_content]
        f_counts = data_extract(content)
    return f_counts


@timer
def update(interval):
    """Function to draw the data read out of hand history in real time

    Parameters
    ----------
    interval : int
        interval necessary to run animation
    """

    ax1.clear()
    ax1sec.clear()
    ax2.clear()
    ax2sec.clear()
    ax3.clear()
    f_counts = data_get()
    busted = {}
    # Chip count
    for c in f_counts[1]:
        ax1.plot(f_counts[1][c][1], f_counts[1][c][0], label=c,  lw=2.5)
        # Draw a vertical line for each bust
        wentBust = [i for i, e in enumerate(f_counts[5][c][2]) if e == 1]
        wentBust = [f_counts[1][c][1][i] for i in wentBust]
        for b in wentBust:
            if b in busted.keys():
                busted[b].append(c)
            else:
                busted.update({b: [c]})
    # Plot the busts
    for k in busted:
        ax1.axvline(k, color="black", lw=0.95,
                    dashes=[6, 4], dash_capstyle="round")
        ax1.annotate("{0}\nwent bust !".format(str(busted[k]).translate(
            {ord(i): None for i in "[]'"})), xy=(
            k, max([max(item[0]) for item in list(f_counts[1].values())])*(12/14)), fontsize=10.5, fontstyle="normal", annotation_clip=False, rotation=33, ha="right", color="black")
    ax1sec.fill_between(
        f_counts[0], 0, f_counts[4], facecolor="black", alpha=0.15)
    ax1sec.set_ylim(ymin=0, ymax=max(
        [max(item[0]) for item in list(f_counts[1].values())])+big_blind)
    ax1sec.axes.yaxis.set_ticklabels([])
    ax1sec.grid(False)
    # Make pretty
    ax1.legend(loc="upper left", prop={'size': 14}, frameon=1)
    ax1.yaxis.set_label_position("right")
    ax1.yaxis.tick_right()
    ax1.set_ylabel('Chip count', fontsize=17)
    ax1.set_xlabel("Hand #", fontsize=17)
    ax1.set_xlim(xmin=0, xmax=max(f_counts[0]))
    ax1.set_ylim(ymin=0, ymax=max(
        [max(item[0]) for item in list(f_counts[1].values())])+big_blind)
    ax1.tick_params(axis='x', labelsize=15)
    ax1.tick_params(axis='y', labelsize=15)
    ax1.axhline(chipCount_start, color="black", lw=1.5,
                dashes=[6, 4], dash_capstyle="round")
    ax1.set_title(f"Chip count at hand # {max(f_counts[0])} ({int(big_blind/2)}/{big_blind} game) with {sum(f_counts[6])} family pots", fontsize=17, fontweight="bold")
    ax1.grid(True, which="major")

    # Win, lose and preflop fold
    preflop_folds = [sum(item[3]) for item in list(f_counts[2].values())]
    all_trials = [len(item[3]) for item in list(f_counts[2].values())]
    percent_preflop_folds = [a/b for a, b in zip(preflop_folds, all_trials)]
    x = np.arange(len(list(f_counts[2].keys())))
    width = .15
    first1 = ax2.bar(x-width-width/2, [sum(item[0]) for item in list(f_counts[2].values())],
                     width, label="Wins w/ showdown", color="g", hatch="")
    first2 = ax2.bar(x-width/2, [sum(item[2]) for item in list(f_counts[2].values())],
                     width, label="Wins w/o showdown", color="yellowgreen", hatch="")
    first3 = ax2.bar(x+width/2, [sum(item[1]) for item in list(f_counts[2].values())],
                     width, label="Losses", color="r", hatch="")
    second = ax2sec.bar(x+width+width/2, percent_preflop_folds, width,
                        label="Preflop fold %", color="dimgray", hatch="")
    # Make pretty
    ax2.legend([first1, first2, first3, second], ["Wins w/ showdown", "Wins w/o showdown",
                                                  "Losses", "Preflop fold %"], loc="upper left", prop={'size': 10}, frameon=True)
    ax2.yaxis.set_label_position("left")
    ax2.yaxis.tick_left()
    ax2.set_ylabel('Count', fontsize=15)
    ax2.set_xticks(x)
    ax2.set_xticklabels(list(f_counts[2].keys()), rotation=40, fontsize=12)
    try:  # corner case: everyone folds to BB. empty string -> max() fails
        ax2.set_ylim(ymin=0, ymax=max([max([sum(item[0]) for item in list(f_counts[2].values())]), max(
            [sum(item[2]) for item in list(f_counts[2].values())]), max([sum(item[1]) for item in list(f_counts[2].values())])])+1)
    except:
        ax2.set_ylim(ymin=0, ymax=1)
    ax2.tick_params(axis='x', labelsize=14)
    ax2.tick_params(axis='y', labelsize=12)
    ax2.set_title("Wins, losses and preflop folds",
                  fontsize=16, fontweight="bold")
    ax2.yaxis.set_major_locator(plt.MaxNLocator(8))
    ax2sec.set_ylabel('Percentage', fontsize=15)
    ax2sec.set_ylim(ymin=0, ymax=.8)
    ax2sec.tick_params(axis='y', labelsize=11)
    ax2sec.yaxis.set_major_locator(plt.MaxNLocator(8))
    ax2.grid(True, which="major")

    # All-in win & loss, rebuys
    x = np.arange(len(list(f_counts[2].keys())))
    width = .15
    ax3.bar(x-width, [sum(item[3]) for item in list(f_counts[5].values())],
            width, label="Re-buys", color="black", hatch="")
    ax3.bar(x, [sum(item[1]) for item in list(f_counts[5].values())],
            width, label="All-ins won", color="g", hatch="")
    ax3.bar(x+width, [sum(item[2]) for item in list(f_counts[5].values())],
            width, label="All-ins lost", color="r", hatch="")
    #ax3.annotate("# of family pots:  {}".format(sum(f_counts[6])), xy=((len(x)-1)/2, max([sum(item[1]) for item in list(f_counts[5].values())]+[sum(item[2]) for item in list(
    #    f_counts[5].values())]+[sum(item[3]) for item in list(f_counts[5].values())])), fontsize=13, fontstyle="normal", ha="center", annotation_clip=False, color="black")
    # Make pretty
    ax3.legend(loc="upper right", prop={'size': 10}, frameon=True)
    ax3.yaxis.set_label_position("right")
    ax3.yaxis.tick_right()
    ax3.set_ylabel('Count', fontsize=15)
    ax3.set_xticks(x)
    ax3.set_xticklabels(list(f_counts[2].keys()), rotation=40, fontsize=12)
    try:  # corner case: everyone folds to BB. empty string -> max() fails
        ax3.set_ylim(ymin=0, ymax=max([max([sum(item[1]) for item in list(f_counts[5].values())]),  max(
            [sum(item[2]) for item in list(f_counts[5].values())]), max([sum(item[3]) for item in list(f_counts[5].values())])])+1)
    except:
        ax3.set_ylim(ymin=0, ymax=1)
    ax3.tick_params(axis='x', labelsize=14)
    ax3.tick_params(axis='y', labelsize=12)
    ax3.set_title("All-in wins, losses and rebuys",
                  fontsize=16, fontweight="bold")
    ax3.grid(True, which="major")

    # sns.despine()
    plt.tight_layout()
    print("updated")


def save_session(spreadsheet, date, name_index, starti_players=5, starti_graph1=63, starti_graph2=81):
    """Function to save session to google spreadsheet

    Parameters
    ----------
    spreadsheet : str
        name of the google spreadsheet
    date : [str
        date of poker night
    name_index : dict
        dictionary containing player names and their PokerStars aliases
    starti_players : int, optional
        starting index for the chip count list in overview, by default 5
    starti_graph1 : int, optional
        starting index for the chip count list of graph 1, by default 63
    starti_graph2 : int, optional
        starting index for the chip count list of graph 2, by default 81

    Returns
    -------
    email_message : str
        message to send via email
    email_recipients : list of str
        contains all the emails of players that participated
    """

    scope = ["https://spreadsheets.google.com/feeds", 'https://www.googleapis.com/auth/spreadsheets',
             "https://www.googleapis.com/auth/drive.file", "https://www.googleapis.com/auth/drive"]

    creds = ServiceAccountCredentials.from_json_keyfile_name(path_creds, scope)

    # To succesfully be authorized, share the spreadsheet on the google account with the email define in the credential.json file.
    client = gspread.authorize(creds)
    spreadsheet = client.open(spreadsheet)  # Open the spreadsheet
    f_counts = data_get()

    # Create new session sheet
    worksheet_no = len(spreadsheet.worksheets())
    current_worksheet = spreadsheet.get_worksheet(worksheet_no-1)
    current_worksheet.duplicate(worksheet_no, new_sheet_name=date)
    current_worksheet = spreadsheet.get_worksheet(worksheet_no)

    # Update overall sheet
    print("Updating spreadsheet ...\n")
    current_worksheet = spreadsheet.get_worksheet(0)
    old_date = current_worksheet.cell(
        starti_players, len(current_worksheet.row_values(starti_players))).value  # save old date for later

    current_worksheet.update_cell(
        starti_players, len(current_worksheet.row_values(starti_players))+1, date)
    current_worksheet.update_cell(
        starti_graph1, len(current_worksheet.row_values(starti_graph1))+1, date)
    current_worksheet.update_cell(
        starti_graph2, len(current_worksheet.row_values(starti_graph2))+1, date)
    for i in range(len(name_index)):
        current_worksheet.update_cell(
            starti_players+1+i, len(current_worksheet.row_values(starti_players)), f"='{date}'!G{9+i}")
        if len(current_worksheet.row_values(starti_players)) > len(string.ascii_lowercase): # start again with the alphabet
            current_worksheet.update_cell(
                starti_graph1+1+i,  len(current_worksheet.row_values(starti_graph1)), f"=SUM($E${6+i}:{'a' + string.ascii_lowercase[len(current_worksheet.row_values(starti_players))-1-len(string.ascii_lowercase)]}{6+i})")
            current_worksheet.update_cell(
                starti_graph2+1+i,  len(current_worksheet.row_values(starti_graph2)), f"={'a' + string.ascii_lowercase[len(current_worksheet.row_values(starti_players))-1-len(string.ascii_lowercase)]}{starti_players+1+i}")
        elif len(current_worksheet.row_values(starti_players)) > 2*len(string.ascii_lowercase):
            print("We are now twice over the column index of A through Z and have to start with AAA...")
        else:
            current_worksheet.update_cell(
                starti_graph1+1+i,  len(current_worksheet.row_values(starti_graph1)), f"=SUM($E${6+i}:{string.ascii_lowercase[len(current_worksheet.row_values(starti_players))-1]}{6+i})")
            current_worksheet.update_cell(
                starti_graph2+1+i,  len(current_worksheet.row_values(starti_graph2)), f"={string.ascii_lowercase[len(current_worksheet.row_values(starti_players))-1]}{starti_players+1+i}")

    # Create new session sheet
    current_worksheet = spreadsheet.get_worksheet(-1)

    # Prepare data
    overview = {}
    email_recipients = []
    with open(path_email, mode="r") as infile:
        reader = csv.reader(infile)
        for rows in reader:
            t_email_list = [rows for rows in reader]
    email_message = f"[automatically created email]\n\nHey guys,\n\nI just updated the excel sheet (https://docs.google.com/spreadsheets/d/1gkXoTGLdAhK8Tqx-yD8Mj2YO2dYev7WBXVQNRhh4EfM/edit?usp=sharing)!\n" + \
        f"I've attached the statistic overview picture to this email and see below for a short summary. As usual, lemme know if something is incorrect.\n\n" + \
        f"See you next time!\nMichel\n\n\nSummary ({max(f_counts[0])} hands played with {sum(f_counts[6])} family pots)\n\n(name : buyins / chip count)\n"

    for i in range(len(name_index)):
        current_name = current_worksheet.get("A"+str(9+i))[0][0]
        for poker_alias in name_index[current_name]:
            if poker_alias in f_counts[1]:
                print("\n---\n")
                # Look up buy-ins
                if "count_buyin" in locals() or "count_buyin" in globals():
                    skip = input(
                        f"{current_name} already has an entry other than {poker_alias} with {count_buyin} buy-ins. If you want to add counts enter 'add'  :  ")
                    old_buyinCount = float(count_buyin)
                count_buyin = sum(f_counts[5][poker_alias][3])+1
                saved_input = input(
                    f"Found {current_name} as {poker_alias} with {count_buyin} buy-ins. Correct? (y/correction)  :  ")
                if saved_input != "y":
                    count_buyin = float(saved_input)
                try:
                    if skip == "add":
                        count_buyin += old_buyinCount
                        skip = ""
                except:
                    pass
                # Look up chip count
                if "chip_count" in locals() or "chip_count" in globals():
                    skip = input(
                        f"{current_name} already has an entry as {poker_alias} with {chip_count} chips and {count_buyin} buy-ins. Skip? (y/n)  :  ")
                    if skip != "n":
                        continue
                chip_count = f_counts[1][poker_alias][0][-1]
                saved_input = input(
                    f"Found {current_name} as {poker_alias} with {chip_count} chips. Correct? (y/correction)  :  ")
                if saved_input != "y":
                    chip_count = int(saved_input)

        if "chip_count" in locals() or "chip_count" in globals():
            saved_input = input(
                f"Saving {current_name} with {chip_count} chips and {count_buyin} buy-ins. Correct? (y/n)  :  ")
            if saved_input != "y":
                chip_count = int(input(
                    f"The chip count of {current_name} ({chip_count}) should be  :  "))
                count_buyin = float(input(
                    f"The buy-ins count of {current_name} ({count_buyin}) should be  :  "))
            f_count_chip, f_count_buyin = chip_count, count_buyin
        else:
            f_count_chip, f_count_buyin = 0, 0

        # Update email_message and add player email to list of recipients
        if f_count_buyin != 0:
            email_message = email_message + \
                f"{current_name} :   {f_count_buyin}   /   {f_count_chip}\n"
            current_email = str(
                t_email_list[t_email_list.index([f'{current_name}'])+1])
            email_recipients.append(current_email.translate(
                {ord(i): None for i in "[];'"}))

        # Update the worksheet
        current_worksheet.update_acell(
            f"F{9+i}", "='"+f"{old_date}"+"'"+f"!H{9+i}")  # gspread has trouble interpreting ' in a full string hence the fragmentation
        current_worksheet.update_acell(f"B{9+i}", f_count_buyin)
        current_worksheet.update_acell(f"D{9+i}", f_count_chip)
        # Attempt clean-up
        try:
            del chip_count, count_buyin
        except:
            pass

    return email_message, email_recipients


def send_email(sender, recipients, subject, message, password=None, path_image=False, date="", smtp_server="smtp.gmail.com", smtp_port=465):
    """Sends an email to all players after the game containing a summary of the poker night and the statistics image attached.

    Parameters
    ----------
    sender : str
        Email of the sender
    recipients : list of strings
        Emails of the recipients
    subject : str
        Subject of the email
    message : str
        Body of the email message
    password : str, optional
        Password to email account, by default None
    path_image : str, optional
        Path to the image that ought to be attached, by default False
    date : str, optional
        Date of the poker night, by default ""
    smtp_server : str, optional
        Email server url, by default "smtp.gmail.com"
    smtp_port : int, optional
        Email server port, by default 465
    """

    if password == False:
        password = input("What's the password of the email account?  ")

    # Subject, body and recipients
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = sender
    if type(recipients) is not list:
        recipients = [recipients]
    msg["To"] = ', '.join(recipients)
    msg.set_content(message)

    # Attachment
    if path_image:
        if type(path_image) is not list:
            path_image = [path_image]
        for c_file in path_image:
            try:
                os.path.isfile(c_file)
            except:
                c_file = str(input(
                    f"{c_file} is no valid file. Type in a correct path:   "))
            with open(c_file, "rb") as f:
                file_data = f.read()
                file_type = imghdr.what(f.name)
            msg.add_attachment(file_data, maintype="image",
                               subtype=file_type, filename=f"Statistics_poker_{date}.{file_type}")

    # Send
    with smtplib.SMTP_SSL(smtp_server, smtp_port) as smtp:
        smtp.login(sender, password)
        smtp.send_message(msg)


### Run the script ###
# * Define some paths and get the most recent hand history file
path_hand = create_dir(
    "C:\\Users\\Michl\\Documents\\GitHub\\pokerstars_reader\\poker_session\\hand_history\\PokerStarMan123")
paths = sorted(Path(path_hand).iterdir(), key=os.path.getmtime)
filename = paths[-1]

path_image_save = create_dir(
    'C:\\Users\\Michl\\Documents\\GitHub\\pokerstars_reader\\poker_session\\stats\\')
path_creds = create_dir(
    "C:\\Users\\Michl\\Documents\\GitHub\\private_projects\\pokerstars\\creds\\") + "creds.json"
path_email = create_dir(
    "C:\\Users\\Michl\\Documents\\GitHub\\private_projects\\pokerstars\\email_list\\") + "email-list.csv"
# Some basic parameters
chipCount_start = 10000
big_blind = 100
name_index = {"Benchi": ["BenchiWang", "MaFak2019", "Mafak2020"], "Dirk": ["JeBoyDirk"], "Ilja": ["Jackall23", "FragileMemory"], "Jan": ["color_singleton"], "Joshua": ["MrOB1reader", "Klemtonius"], "Manon": [
    "Manon541", "Manon947", "MnnM150", "manon327"], "Michel": ["Duke", "FantasticDouble", "PokerStarMan123"], "Yair": ["yairpinto"], "Steven": ["JachtSlot"], "Jasper": ["HighCardJasper"], "Docky": ["dhduncan", "dddocky"], "Ruben": ["Rubeneero"], "Yavor": ["RichRick1337", "poorrick1338"],
    "Rogier": ["rogierk449"], "Clayton": ["appositive"]}
date = input("What's the date?   :  ")


# * Actually start the showing the graph
style.use("seaborn-dark")
fig = plt.figure(figsize=[19, 10])
ax1 = plt.subplot2grid((6, 6), (0, 0), rowspan=4, colspan=6, fig=fig)
ax2 = plt.subplot2grid((6, 6), (4, 0), rowspan=2, colspan=3, fig=fig)
ax3 = plt.subplot2grid((6, 6), (4, 3), rowspan=2, colspan=3, fig=fig)
ax1sec = ax1.twinx()
ax2sec = ax2.twinx()

# Animate
ani = animation.FuncAnimation(fig, update, interval=5000)
plt.show()

savePics = input("Safe pics (y/n)?   :  ")
if savePics == 'y':
    fig.savefig(path_image_save+f"{date}.png", format="png", dpi=400, bbox_inches='tight')
    fig.savefig(path_image_save+f"{date}.svg", format="svg", bbox_inches='tight')

# * Save to Google sheets?
saveSession = input("Upload (y/n)?   :  ")
if saveSession == 'y':
    email_message, email_recipients = save_session(
        spreadsheet="lockdown-poker", date=date, name_index=name_index)

    # * Send email?
    print("Email message prepared:")
    print(email_message)
    s_email = input("Send an overview email ? (y/n)  :  ")
    if s_email == "y":
        send_email(sender=os.environ.get("EMAIL_ADDRESS_GMAIL"), recipients=email_recipients, subject=f"Overview Poker night {date}", message=email_message, password=os.environ.get("EMAIL_PASSWORD_GMAIL"), date=date, path_image=path_image_save+f"{date}.png")

print("\nDone!")
