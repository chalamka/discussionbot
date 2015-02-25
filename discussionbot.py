# Discussion Bot:  create weekly discussion posts and help promote discussion
# throughout the week by occasionally checking for comments and promoting them
# by adding them to the original post for easier access.

import logging
import getopt
import sys
import json
import praw
import praw.helpers
import praw.errors
import re
import datetime as dt

logger = logging.getLogger(__name__)
logger.addHandler(logging.StreamHandler())


BOT_CONFIG = "botconfig.json"

def usage():
    print("invalid option.\nvalid options are -v --verbose")

def load_config(filename):
    try:
        with open(filename) as fp:
            return json.load(fp)
    except IOError:
        logger.critical("Failed to load discussion configuration file \"%s\"" % filename)
        sys.exit(2)

def write_json(filename, to_write):
    with open(filename, 'w') as fp:
        return json.dump(to_write, fp)

def new_submission(r, config, previous_threads):
    logger.info("Creating a new submission...")
    subreddit = config['subreddit']

    title = config['title']
    title = re.sub("MM/DD/YY", dt.datetime.now().strftime("[%m/%d/%y]"),title)

    body = config['body']
    body = re.sub("MM/DD/YY", dt.datetime.now().strftime("[%m/%d/%y]"),body)
    body += "\n\nPrevious Weekly Threads:"
    for thread in previous_threads['previous_submissions']:
        previous_submission = r.get_submission(submission_id='%s' % thread)
        body += "\n\n* [" + previous_submission.title + "]" + "(" + previous_submission.url + ")"

    logger.info("New post: \"%s\"" % title)
    submission = r.submit(subreddit, title, text=body, save=True)
    logger.info("New post \"%s\" submitted to /r/%s\n" % (title, subreddit))

    return submission

def update_sidebar(r, config, submission):
    logger.info("Updating sidebar, subreddit = %s" % config['subreddit'])
    subreddit = r.get_subreddit(config['subreddit'])
    settings = r.get_settings(subreddit)
    sidebar = settings['description']

    flag_re = config['startflag'] + r".*?" + config['endflag']

    #'(\[]\(#FLAG\)).*?(\[]\(/FLAG\))'
    sidebar = re.sub(flag_re,
                     '\\1\\2',
                     sidebar,
                     flags=re.DOTALL)

    opening_marker = re.compile(config['startflag'])
    start_flag = re.search(opening_marker, sidebar)

    #format a string to contain the submission title as a link to the thread
    submission_link = "[" + submission.title + "]" + "(" + submission.url + ")"

    try:
        marker_pos = start_flag.end()
        sidebar = sidebar[:marker_pos] + submission_link + sidebar[marker_pos:]
        logger.info("updated sidebar:\n%s" % sidebar)
    except ValueError:
        # Substring not found
        logger.info("Flags not found.")

    subreddit.update_settings(description=sidebar)

def main(args):
    level = logging.CRITICAL

    #get command line flags and set logging level
    try:
        opts, args, = getopt.getopt(args, "v", "verbose")
    except getopt.GetoptError:
        #could not get options from command line
        usage()
        sys.exit(1)

    for opt, arg in opts:
        if opt in ("-v", "--verbose"):
            level=logging.INFO
    source_file = "".join(args)
    logger.setLevel(level)
    
    logger.info("In main function\nLoading config from %s" % source_file)

    #load config files
    config = load_config(source_file)
    bot = load_config(BOT_CONFIG)
    previous_submissions = load_config(config['previous_submissions'])

    #authenticate reddit user
    logger.info("Configs loaded successfully\n\nAttempting to authenticate with Reddit...")
    try:
        r = praw.Reddit('discussionbot')
        r.login(bot['username'], bot['password'])
    except praw.errors.APIException:
        logger.critical("Could not authenticate with Reddit.  Likely an incorrect username/password")
        sys.exit(3)
    logger.info("Successfully authenticated %s\nSubreddit: %s\n" % (bot['username'], bot['subreddit']))

    # create a new discussion thread based on config
    # update sidebar to include a link
    # finally save the submission ID for future use
    submission = new_submission(r, config, previous_submissions)
    update_sidebar(r, config, submission)
    previous_submissions['previous_submissions'].append(submission.id)
    write_json(config['previous_submissions'], previous_submissions)

if __name__ == '__main__':
    main(sys.argv[1:])