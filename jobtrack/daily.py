"""
The line of the day: one short, original line of encouragement for job
seekers, the same for everyone on a given date, changing every day.
"""

from datetime import date

DAILY_LINES = [
    "Every application is a door you knocked on. Keep knocking.",
    "A rejection only tells you where you don't fit. Somewhere, you do.",
    "Your résumé gets you the call. Your follow-up gets you remembered.",
    "The job you want may be posted today. Be the one who sees it first.",
    "Nobody hires the person who almost applied.",
    "Ten sent applications beat one perfect draft.",
    "Silence after applying isn't a no. It's a queue.",
    "Skills are built in the hours nobody claps for.",
    "Interview nerves mean you got far enough to be nervous.",
    "A no today is information. Use it, then send the next one.",
    "Your network is bigger than your contact list. Say hello to someone new.",
    "The offer letter is written by a hundred ordinary days like this one.",
    "Fix one line on your résumé today. Tomorrow it reads better.",
    "Recruiters can't find you while you wait to be found.",
    "Tired is fine. Stopped is not.",
    "Every company you research makes the next interview easier.",
    "One good question in an interview beats three rehearsed answers.",
    "Momentum is a skill. Practice it daily.",
    "You don't need to feel ready. You need to press submit.",
    "Somewhere a hiring manager is hoping the next candidate is you.",
    "The gap between you and the offer is just more reps.",
    "Your story matters more than your title. Tell it well.",
    "Applications are seeds. Some sprout late.",
    "Celebrate the interview, not only the offer.",
    "Read the job description twice. Answer it once, clearly.",
    "Good things come to those who follow up.",
    "Choose your search over your scroll.",
    "The best time to update your profile was yesterday. The next best is now.",
    "Confidence is built from evidence. Collect some today.",
    "A two-minute thank-you email lasts the whole hiring decision.",
    "If the door is closed, try the window: referrals, events, alumni.",
    "Your first job is getting the job. Clock in.",
    "Every 'we went another direction' points you toward yours.",
    "Practice out loud. Interviews are spoken, not written.",
    "Small wins count: a reply, a call, a new skill. Write them down.",
    "The market is tough. So are you.",
    "Apply where you match, and stretch where you learn fast.",
    "Keep your tracker honest. It shows you what's working.",
    "A rested mind writes a better cover letter.",
    "You're one yes away. Keep collecting no's until you find it.",
    "Today's effort is tomorrow's interview.",
    "Make one connection today that you didn't have yesterday.",
    "Show your work. Projects speak when you can't.",
    "The job search is a season, not a sentence.",
    "Put a number in that bullet point. Numbers make it believable.",
    "Every expert in that role was once the new hire.",
    "Ask for the referral. The worst answer is the one you already have.",
    "Consistency outruns talent that takes days off.",
    "Treat the search like a job, and the job will come.",
    "Somebody has to get this job. Make the case that it's you.",
]


def line_for(day=None):
    day = day or date.today()
    return DAILY_LINES[day.toordinal() % len(DAILY_LINES)]
