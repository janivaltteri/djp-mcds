import json
from django.contrib.auth import get_user_model

print('executing create-users.py for fileserver')

UserModel = get_user_model()

with open('userlist.json', 'r') as f:
    ul = json.load(f)

for i in range(len(ul['user'])):
    uname = ul['user'][i]['name']
    upass = ul['user'][i]['pass']
    ustaf = ul['user'][i]['staff']
    if not UserModel.objects.filter(username=uname).exists():
        user = UserModel.objects.create_user(uname, password=upass)
        if ustaf == 'yes':
            user.is_staff = True
        user.save()
        print('created user ' + uname)
    else:
        print('skipped existing user ' + uname)
