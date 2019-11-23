"""
This is the main script. Pick provides a small CLI.
"""

from datetime import datetime
from itertools import dropwhile, takewhile
import sys
import pandas as pd
from pick import pick
import instaloader
from instaloader import Profile


def query_yes_no(question, default="yes"):
    """Ask yes/no question"""
    valid = {"yes": True, "y": True, "ye": True,
             "no": False, "n": False}
    if default is None:
        prompt = " [y/n] "
    elif default == "yes":
        prompt = " [Y/n] "
    elif default == "no":
        prompt = " [y/N] "
    else:
        raise ValueError("invalid default answer: '%s'" % default)

    while True:
        sys.stdout.write(question + prompt)
        choice = input().lower()
        if default is not None and choice == '':
            return valid[default]
        elif choice in valid:
            return valid[choice]
        else:
            sys.stdout.write("Please respond with 'yes' or 'no' "
                             "(or 'y' or 'n').\n")


def do_login(L):
    """wrapper for instagram login"""
    username = input('What is your Instagram username?')
    try:
        L.interactive_login(username)
    except:
        print("Provided username does not exist.. Try again.\n")
        do_login(L)
        

def choose_target(login):
    """Uses chooses which type of content to query."""
    nologin_targets = ['public profile', 'hashtag', 'single post']
    login_targets = ['private profile', 'location id',
                     'story', 'feed', 'saved']
    target_options = nologin_targets
    if login:
        # Make more options available
        target_options.extend(login_targets)
    titel = '''Please choose target.
See https://instaloader.github.io/basic-usage.html#what-to-download'''
    option, _ = pick(target_options, titel)
    return option


def get_instaloder_options():
    """Lets user select what they want to download"""
    options = ['pictures', 'videos', 'thumbnails']
    title = 'Which of these media do you want to download? (SPACE to mark)'
    selected = pick(options, title, multi_select=True)
    selected = [s[0] for s in selected]      
    return selected


def period_reduce():
    """Only downloads for a specific period. Doesnt work very well."""
    date_entry1 = input('Enter a "since" date in YYYY-MM-DD format. ')
    date_entry2 = input('Enter a "until" date in YYYY-MM-DD format. ')
    try:
        SINCE = datetime.strptime(date_entry1, '%Y-%m-%d')
        UNTIL = datetime.strptime(date_entry2, '%Y-%m-%d')
    except ValueError:
        print("Invald date. Try again.\n")
        return period_reduce()
    print('\nBeginning harvest...\n\n')
    limited_posts = takewhile(lambda p: p.date > UNTIL,
                              dropwhile(lambda p: p.date > SINCE,
                                        posts))
    return limited_posts


def parse_locations(row):
    """Turn location objects into dictionary for tabular representation."""
    if row:
        return {
            'loc_id': row.id,
            'loc_lat': row.lat,
            'loc_lng': row.lng,
            'loc_name': row.name,
        }
    else:
        return ''


def ask_n_post_lim():
    """Ask user post limit"""
    n_post_lim = input("How many posts?")
    try:
        result = int(n_post_lim)
    except ValueError:
        print("Please input an integer")
        return ask_n_post_lim()
    return result


# What do you want to download?
selected = get_instaloder_options()
if 'pictures' in selected:
    pictures = True
else:
    pictures = False
if 'videos' in selected:
    videos = True
else:
    videos = False
if 'thumbnails' in selected:
    thumbnails = True
else:
    thumbnails = False

# Do you want to compress?
compress = query_yes_no("Do you want to compress jsons?", default="yes")

# Do you want to log in?
LOGIN = query_yes_no("Do you want to log in?", default="no")

# Initiatilize instaloader with user settings
L = instaloader.Instaloader(download_pictures=pictures,
                            download_videos=videos,
                            download_video_thumbnails=thumbnails,
                            compress_json=compress,
                            filename_pattern='{shortcode}')

if LOGIN:
    do_login(L)

# Chose target (like hashtag, profile), based on whether logged in
target = choose_target(LOGIN)

# What do you want to query for?
query = input(f'Which {target} do you want to search for? \n')

# Only in time period?
period_only = query_yes_no('''
Do you want to limit your search to a specific period?
(Experimental)''',
                           default="no")

# Only n posts?
n_post_lim = None  # Default
n_post_only = query_yes_no("Do you limit your search to N number of posts?",
                           default="no")
if n_post_only:
    n_post_lim = ask_n_post_lim()

# Get posts based on user settings
if target == 'public profile':
    profile = Profile.from_username(L.context, query)
    posts = profile.get_posts()
if target == 'hashtag':
    posts = L.get_hashtag_posts(query)
if target == 'location id':
    posts = L.get_location_posts(query)

# These are the post attributes that will become dataframe columns
post_attr = [
    'shortcode',
    'mediaid',
    'owner_username',
    'owner_id',
    'date_local',
    'date_utc',
    'url',
    'typename',
    'caption',
    'caption_hashtags',
    'caption_mentions',
    'pcaption',
    'tagged_users',
    'video_url',
    'video_view_count',
    'likes',
    'comments',
    'location'
]

# Initialize main dataframe and comment list
data = pd.DataFrame(columns=post_attr)
all_comments = []

# Download data
while True:
    try:
        # Apply time limit to post generator
        if period_only:
            posts = period_reduce()

        # Apply n limit to post generator, like posts[:n_post_lim]
        if n_post_only:
            posts = (x for _, x in zip(range(n_post_lim), posts))

        print('\nBeginning harvest. Ctrl-C to stop.\n\n')
        for post in posts:
            L.download_post(post, target=query)
            post_info = [getattr(post, attr) for attr in post_attr]

            # Put postinfo in dataframe
            data = data.append(pd.Series(
                dict(zip(data.columns, post_info))),
                               ignore_index=True)

            # Get comments
            if post.comments > 0:
                for comment in post.get_comments():
                    all_comments.append({
                        'post_shortcode': post.shortcode,
                        'answer_to_comment': '',
                        'created_at_utc': comment.created_at_utc,
                        'id': comment.id,
                        'likes_count': comment.likes_count,
                        'owner': comment.owner.userid,
                        'text': comment.text})
                    if hasattr(comment, 'answers'):
                        for answer in comment.answers:
                            all_comments.append({
                                'post_shortcode': post.shortcode,
                                'answer_to_comment': comment.id,
                                'created_at_utc': answer.created_at_utc,
                                'id': answer.id,
                                'likes_count': answer.likes_count,
                                'owner': answer.owner.userid,
                                'text': answer.text})
        break
    except KeyboardInterrupt:
        break


"""
CLEANING SECTION
"""

# Turn list columns into strings
data[['caption_hashtags',
      'caption_mentions',
      'tagged_users']] = data[[
          'caption_hashtags',
          'caption_mentions',
          'tagged_users']].applymap(
              lambda lst: ','.join(lst)
          )

# Turn location column into dicts, then seperate columns
data['location'] = data['location'].apply(parse_locations)
data = pd.concat([data, data['location'].apply(pd.Series)], axis=1)
data = data.drop('location', errors='ignore')

# Save data and comments
data.to_csv('output.csv', index=False)
comments_df = pd.DataFrame(all_comments)
comments_df.to_csv('comments.csv')
