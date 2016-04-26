from django.conf import settings
from django.contrib.auth.models import User
from zwp.models import DataSource
from zwp.metadata import Users


class DataSourceBackend(object):
    """
    Authenticate agains users defined in users.ini in the data directory.
    """
    def authenticate(self, username=None, password=None):
        for ds, opts in filter(
            lambda v: v[1].get('auth', False),
            settings.ZWP_DATA_SOURCES.items()
        ):
            u = Users(DataSource(ds, opts))

            if u.authenticate(username, password):
                try:
                    user = User.objects.get(username=username)

                except User.DoesNotExist:
                    user = User.objects.create(
                        username=username,
                        password='in users.ini',
                    )

                return user

        return None
    
    def get_user(self, user_id):
        try:
            return User.objects.get(pk=user_id)

        except User.DoesNotExist:
            return None