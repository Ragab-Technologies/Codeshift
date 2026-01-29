"""
Old Django URL patterns that need migration.
Uses deprecated patterns from Django 3.2 that changed in Django 4.x+
"""
from django.conf.urls import url, include  # Deprecated: use django.urls
from django.urls import path, re_path
from django.views.generic import TemplateView

# Old pattern: Using deprecated url() function with regex
urlpatterns = [
    # Deprecated: url() with regex - should use path() or re_path()
    url(r'^articles/(?P<year>[0-9]{4})/$', 'articles.views.year_archive'),  # String view reference deprecated
    url(r'^articles/(?P<year>[0-9]{4})/(?P<month>[0-9]{2})/$', 'articles.views.month_archive'),
    url(r'^articles/(?P<pk>[0-9]+)/$', 'articles.views.article_detail'),
    
    # Old pattern: Using regex groups without named parameters
    url(r'^blog/([0-9]+)/$', 'blog.views.post_detail'),  # Unnamed group
    
    # Old pattern: Using include with namespace without app_name
    url(r'^api/', include('api.urls', namespace='api')),  # Deprecated namespace usage
    
    # Old pattern: Using extra_context (deprecated in some contexts)
    url(r'^about/$', TemplateView.as_view(template_name='about.html'), 
        {'extra_context': {'title': 'About'}}),
]
