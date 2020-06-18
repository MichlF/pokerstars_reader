
# * Import modules
import gspread  # for manipulating google sheets https://gspread.readthedocs.io/en/latest/index.html
import math
import os
import string
import seaborn as sns
import numpy as np
import matplotlib.animation as animation
import matplotlib.pyplot as plt
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

# Define some paths and get the most recent hand history file
handpath = "C:\\Users\\Michl\\AppData\\Local\\PokerStars.EU\\HandHistory\\"
paths = sorted(Path(handpath).iterdir(), key=os.path.getmtime)
filename = paths[-1]
try:
    os.makedirs('C:\\Users\\Michl\\Desktop\\poker_session\\')
except OSError:
    print("Folders already exist. Skipped!")
finally:
    savedir = 'C:\\Users\\Michl\\Desktop\\poker_session\\'
# Some basic parameters
chipCount_start = 10000
bigBlind = 100
date = input("What's the date?   -  ")

# * Functions


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


def extractData(rawlines):
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
    count_hand : dict
        Counter for overall hands played
    each_rake : dict
        List of values for rake per hand
    each_potsize : dict
        List of values for pot size per hand
    each_allin : dict
        For each player name (dict key) list of four lists of 0/1 for each hand played: all-in, all-in won, bust, rebuy
    """

    each_chips, each_wins, count_hand, each_rake, each_potsize, countAllIn = [
        {}, {}, [0], [.01e-20], [.01e-20], {}]
    for line in rawlines:
        words = line.split()
        if len(words) > 4 and words[0] not in ['***', 'Board', 'Table']:
            # Hand count
            if words[-1] == "ET":
                count_hand.append(count_hand[-1]+1)
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
                if words[2] in countAllIn.keys():
                    [item.append(0) for item in countAllIn[words[2]]]
                    # Check if player went bust and rebought
                    if countAllIn[words[2]][2][-2]:
                        countAllIn[words[2]][3][-1] = 1
                else:
                    countAllIn[words[2]] = [[0, 0], [0, 0], [0, 0], [0, 0]]
                # Update wins
                if words[2] in each_wins.keys():
                    [item.append(0) for item in each_wins[words[2]]]
                else:
                    each_wins[words[2]] = [[0, 0], [0, 0], [0, 0], [0, 0]]
            # All-In
            elif words[-1] == "all-in":
                # strip the semicolon from the name
                words_stripped = words[0].translate(
                    {ord(i): None for i in ':'})
                countAllIn[words_stripped][0][-1] = 1
            # Win w/ showdown count
            elif "won" in words:
                each_wins[words[2]][0][-1] = 1
                # if all-in and won
                if countAllIn[words[2]][0][-1] == 1:
                    countAllIn[words[2]][1][-1] = 1
            # Lost count
            elif "lost" in words or "mucked" in words:
                each_wins[words[2]][1][-1] = 1
                # if all-in and lost/mucked, player went bust
                if countAllIn[words[2]][0][-1] == 1:
                    countAllIn[words[2]][2][-1] = 1
            # Won w/o showdown count
            elif words[-2] == "collected":
                each_wins[words[2]][2][-1] = 1
                # if all-in and won
                if countAllIn[words[2]][0][-1] == 1:
                    countAllIn[words[2]][1][-1] = 1
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

    return count_hand, each_chips, each_wins, each_rake, each_potsize, countAllIn


def getData():
    """Function that opens the hand history file and calls extract data function

    Returns
    -------
    list of lists
        contains all information returned by extractData()
    """

    with open(filename) as raw_file:
        raw_content = raw_file.readlines()
        content = [x.strip() for x in raw_content]
        finalCounts = extractData(content)
    return finalCounts


# Start drawing
# style.use("fivethirtyeight")
# style.use("seaborn")
style.use("seaborn-dark")
# style.use("Solarize_Light2")
# style.use("ggplot")
fig = plt.figure(figsize=[19, 10])
ax1 = plt.subplot2grid((6, 6), (0, 0), rowspan=4, colspan=6, fig=fig)
ax2 = plt.subplot2grid((6, 6), (4, 0), rowspan=2, colspan=3, fig=fig)
ax3 = plt.subplot2grid((6, 6), (4, 3), rowspan=2, colspan=3, fig=fig)
ax1sec = ax1.twinx()
ax2sec = ax2.twinx()


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
    finalCounts = getData()
    busted = {}
    # Chip count
    for c in finalCounts[1]:
        ax1.plot(finalCounts[1][c][1], finalCounts[1][c][0], label=c,  lw=2.5)
        # Draw a vertical line for each bust
        wentBust = [i for i, e in enumerate(finalCounts[5][c][2]) if e == 1]
        wentBust = [finalCounts[1][c][1][i] for i in wentBust]
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
            k, max([max(item[0]) for item in list(finalCounts[1].values())])*(12/14)), fontsize=10.5, fontstyle="normal", annotation_clip=False, rotation=33, ha="right", color="black")
    ax1sec.fill_between(
        finalCounts[0], 0, finalCounts[4], facecolor="black", alpha=0.15)
    ax1sec.set_ylim(ymin=0, ymax=max(
        [max(item[0]) for item in list(finalCounts[1].values())])+bigBlind)
    ax1sec.axes.yaxis.set_ticklabels([])
    ax1sec.grid(False)
    # Make pretty
    ax1.legend(loc="upper left", prop={'size': 14}, frameon=1)
    ax1.yaxis.set_label_position("right")
    ax1.yaxis.tick_right()
    ax1.set_ylabel('Chip count', fontsize=17)
    ax1.set_xlabel("Hand #", fontsize=17)
    ax1.set_xlim(xmin=0, xmax=max(finalCounts[0]))
    ax1.set_ylim(ymin=0, ymax=max(
        [max(item[0]) for item in list(finalCounts[1].values())])+bigBlind)
    ax1.tick_params(axis='x', labelsize=15)
    ax1.tick_params(axis='y', labelsize=15)
    ax1.axhline(chipCount_start, color="black", lw=1.5,
                dashes=[6, 4], dash_capstyle="round")
    ax1.set_title("- Chip count at hand #{0} ({1}/{2} game) -".format(
        max(finalCounts[0]), int(bigBlind/2), bigBlind), fontsize=17, fontweight="bold")
    ax1.grid(True, which="major")
    # ax1.yaxis.set_major_locator(plt.MaxNLocator(8))

    # Win, lose and preflop fold
    allPreflopFolds = [sum(item[3]) for item in list(finalCounts[2].values())]
    allTrials = [len(item[3]) for item in list(finalCounts[2].values())]
    percentagePreflopFold = [a/b for a, b in zip(allPreflopFolds, allTrials)]
    width = .15
    x = np.arange(len(list(finalCounts[2].keys())))
    first1 = ax2.bar(x-width-width/2, [sum(item[0]) for item in list(finalCounts[2].values())],
                     width, label="Wins w/ showdown", color="g", hatch="")
    first2 = ax2.bar(x-width/2, [sum(item[2]) for item in list(finalCounts[2].values())],
                     width, label="Wins w/o showdown", color="yellowgreen", hatch="")
    first3 = ax2.bar(x+width/2, [sum(item[1]) for item in list(finalCounts[2].values())],
                     width, label="Losses", color="r", hatch="")
    second = ax2sec.bar(x+width+width/2, percentagePreflopFold, width,
                        label="Preflop fold", color="dimgray", hatch="")
    # Make pretty
    ax2.legend([first1, first2, first3, second], ["Wins w/ showdown", "Wins w/o showdown",
                                                  "Losses", "Preflop fold"], loc="upper left", prop={'size': 10}, frameon=True)
    ax2.yaxis.set_label_position("left")
    ax2.yaxis.tick_left()
    ax2.set_ylabel('Count', fontsize=15)
    ax2.set_xticks(x)
    ax2.set_xticklabels(list(finalCounts[2].keys()), rotation=40, fontsize=12)
    try:  # corner case: everyone folds to BB. empty string -> max() fails
        ax2.set_ylim(ymin=0, ymax=max([max([sum(item[0]) for item in list(finalCounts[2].values())]), max(
            [sum(item[2]) for item in list(finalCounts[2].values())]), max([sum(item[1]) for item in list(finalCounts[2].values())])])+1)
    except:
        ax2.set_ylim(ymin=0, ymax=1)
    ax2.tick_params(axis='x', labelsize=14)
    ax2.tick_params(axis='y', labelsize=12)
    ax2.set_title("- Wins, losses and preflop folds -",
                  fontsize=16, fontweight="bold")
    ax2.yaxis.set_major_locator(plt.MaxNLocator(8))
    ax2sec.set_ylabel('Percentage', fontsize=15)
    # ax2sec.set_yticks(
    #    [x * ((100/5)/100) for x in range(0, 8)])
    ax2sec.set_ylim(ymin=0, ymax=.8)
    ax2sec.tick_params(axis='y', labelsize=11)
    ax2sec.yaxis.set_major_locator(plt.MaxNLocator(8))
    ax2.grid(True, which="major")

    # All-in win & loss, rebuys
    width = .15
    ax3.bar(x-width, [sum(item[3]) for item in list(finalCounts[5].values())],
            width, label="Re-buys", color="black", hatch="")
    ax3.bar(x, [sum(item[1]) for item in list(finalCounts[5].values())],
            width, label="All-ins won", color="g", hatch="")
    ax3.bar(x+width, [sum(item[2]) for item in list(finalCounts[5].values())],
            width, label="All-ins lost", color="r", hatch="")
    # Make pretty
    ax3.legend(loc="upper right", prop={'size': 10})
    ax3.yaxis.set_label_position("right")
    ax3.yaxis.tick_right()
    ax3.set_ylabel('Count', fontsize=15)
    ax3.set_xticks(x)
    ax3.set_xticklabels(list(finalCounts[2].keys()), rotation=40, fontsize=12)
    try:  # corner case: everyone folds to BB. empty string -> max() fails
        ax3.set_ylim(ymin=0, ymax=max([max([sum(item[1]) for item in list(finalCounts[5].values())]),  max(
            [sum(item[2]) for item in list(finalCounts[5].values())]), max([sum(item[3]) for item in list(finalCounts[5].values())])])+1)
    except:
        ax3.set_ylim(ymin=0, ymax=1)
    ax3.tick_params(axis='x', labelsize=14)
    ax3.tick_params(axis='y', labelsize=12)
    ax3.set_title("- All-in wins, losses and rebuys -",
                  fontsize=16, fontweight="bold")
    ax3.grid(True, which="major")
    # ax3.yaxis.set_major_locator(plt.MaxNLocator(8))

    # sns.despine()
    plt.tight_layout()
    print("updated")


# Show graph
ani = animation.FuncAnimation(fig, update, interval=5000)
plt.show()
fig.savefig(savedir+"PokerOn_{}.svg".format(date), bbox_inched='tight')

# Save?
saveSession = input("Do you wanna save & upload (y/n)?   -  ")

if saveSession == 'y':
    scope = ["https://spreadsheets.google.com/feeds", 'https://www.googleapis.com/auth/spreadsheets',
             "https://www.googleapis.com/auth/drive.file", "https://www.googleapis.com/auth/drive"]

    creds = ServiceAccountCredentials.from_json_keyfile_name(
        "C:\\Users\\Michl\\Desktop\\creds\\creds.json", scope)

    # To succesfully be authorized, share the spreadsheet on the google account with the email define in the credential.json file.
    client = gspread.authorize(creds)

    spreadsheet = client.open("lockdown-poker")  # Open the spreadsheet

    finalCounts = getData()

    # Create new session sheet
    worksheet_no = len(spreadsheet.worksheets())
    current_worksheet = spreadsheet.get_worksheet(worksheet_no-1)
    current_worksheet.duplicate(worksheet_no, new_sheet_name=date)
    current_worksheet = spreadsheet.get_worksheet(worksheet_no)

    # Update overall sheet
    current_worksheet = spreadsheet.get_worksheet(0)
    old_date = current_worksheet.cell(
        5, len(current_worksheet.row_values(5))).value  # save old date for later

    current_worksheet.update_cell(
        5, len(current_worksheet.row_values(5))+1, date)
    current_worksheet.update_cell(
        63, len(current_worksheet.row_values(63))+1, date)
    current_worksheet.update_cell(
        81, len(current_worksheet.row_values(81))+1, date)
    for i in range(12):
        current_worksheet.update_cell(
            6+i, len(current_worksheet.row_values(5)), "='{}'!G{}".format(date, 9+i))
        current_worksheet.update_cell(
            64+i,  len(current_worksheet.row_values(63)), "=SUM($E${0}:{1}{0})".format(6+i, string.ascii_lowercase[len(current_worksheet.row_values(5))-1]))
        current_worksheet.update_cell(
            82+i,  len(current_worksheet.row_values(81)), "={}{}".format(string.ascii_lowercase[len(current_worksheet.row_values(5))-1], 6+i))

    # Create new session sheet
    current_worksheet = spreadsheet.get_worksheet(-1)

    nameIndex = {"Benchi": ["BenchiWang", "MaFak2019", "Mafak2020"], "Dirk": ["JeBoyDirk"], "Ilja": ["Jackall23", "FragileMemory"], "Jan": ["color_singleton"], "Joshua": ["MrOB1reader", "Klemtonius"], "Manon": [
        "Manon541", "Manon947"], "Michel": ["Duke"], "Yair": ["yairpinto"], "Steven": ["JachtSlot"], "Jasper": ["HighCardJasper"], "Docky": ["dhduncan", "dddocky"], "Ruben": ["Rubeneero"]}

    for i in range(12):
        currentName = current_worksheet.get("A"+str(9+i))[0][0]
        for name in nameIndex[currentName]:
            if name in finalCounts[1]:
                print("\n---\n")
                # Look up buy-ins
                if "buyinCount" in locals() or "buyinCount" in globals():
                    skip = input(
                        "{} already has an entry other than {} with {} buy-ins. If you want to add counts enter 'add'  :  ".format(currentName, name, buyinCount))
                    old_buyinCount = int(buyinCount)
                buyinCount = sum(finalCounts[5][name][3])+1
                savedInput = input(
                    "Found {} as {} with {} buy-ins. Correct? (y/correction)  :  ".format(currentName, name, buyinCount))
                if savedInput != "y":
                    buyinCount = int(savedInput)
                try:
                    if skip == "add":
                        buyinCount += old_buyinCount
                        skip = ""
                except:
                    pass
                # Look up chip count
                if "chipCount" in locals() or "chipCount" in globals():
                    skip = input(
                        "{} already has an entry as {} with {} chips and {} buy-ins. Skip? (y/n)  :  ".format(currentName, name, chipCount, buyinCount))
                    if skip != "n":
                        continue
                chipCount = finalCounts[1][name][0][-1]
                savedInput = input(
                    "Found {} as {} with {} chips. Correct? (y/correction)  :  ".format(currentName, name, chipCount))
                if savedInput != "y":
                    chipCount = int(savedInput)

        if "chipCount" in locals() or "chipCount" in globals():
            savedInput = input(
                "Save {} with {} chips and {} buy-ins. Correct? (y/n)  :  ".format(currentName, chipCount, buyinCount))
            if savedInput != "y":
                f_chipCount = int(input(
                    "The chip count of {} ({}) should be  :  ".format(currentName, chipCount)))
                f_buyinCount = int(input(
                    "The buy-ins count of {} ({}) should be  :  ".format(currentName, buyinCount)))
            f_chipCount, f_buyinCount = chipCount, buyinCount
        else:
            f_chipCount, f_buyinCount = 0, 0

        # Update the worksheet
        current_worksheet.update_acell(
            "F{}".format(9+i), "='"+"{}".format(old_date)+"'"+"!H{}".format(9+i))  # gspread has trouble interpreting ' in a full string hence the fragmentation
        current_worksheet.update_acell("B{}".format(9+i), f_buyinCount)
        current_worksheet.update_acell("D{}".format(9+i), f_chipCount)
        try:
            del chipCount, buyinCount
        except:
            pass

print("\nDone!")
