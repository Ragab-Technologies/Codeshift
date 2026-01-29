"""
Old MongoEngine patterns that need migration.
Uses deprecated patterns from mongoengine 0.23.x that changed in newer versions
"""
from mongoengine import (
    Document, EmbeddedDocument, DynamicDocument,
    StringField, IntField, ListField, DictField,
    ReferenceField, EmbeddedDocumentField, DateTimeField,
    connect, register_connection
)
from mongoengine.queryset import QuerySet
from mongoengine.connection import get_connection, get_db

# Old pattern: Using deprecated connection configuration
# Deprecated: Using mongoengine.connect with old parameters
connect(
    'mydb',
    host='localhost',
    port=27017,
    # Deprecated: Using username/password instead of authentication_source
    username='admin',
    password='password',
    # Old pattern: Using deprecated authentication parameters
    authentication_source='admin',
    # Deprecated: Using read_preference as string
    read_preference='PRIMARY',
    # Old pattern: Using deprecated maxPoolSize
    maxPoolSize=100
)

# Old pattern: Using deprecated Document meta options
class OldStyleDocument(Document):
    """Old Document pattern with deprecated meta options."""
    name = StringField(required=True, max_length=100)
    # Deprecated: Using db_field with old patterns
    value = IntField(db_field='val')
    # Old pattern: Using deprecated required parameter style
    description = StringField(required=False, default=None)
    
    meta = {
        # Deprecated: Using collection instead of collection_name in some contexts
        'collection': 'old_documents',
        # Old pattern: Using deprecated indexes format
        'indexes': [
            {'fields': ['name'], 'unique': True},
            {'fields': ['value'], 'sparse': True},
            # Deprecated: Using cls option
            {'fields': ['name', 'value'], 'cls': False}
        ],
        # Deprecated: Using allow_inheritance
        'allow_inheritance': True,
        # Old pattern: Using deprecated strict option
        'strict': False
    }

# Old pattern: Using deprecated EmbeddedDocument
class OldEmbeddedDoc(EmbeddedDocument):
    """Old embedded document pattern."""
    # Deprecated: Using old field options
    street = StringField(max_length=200)
    city = StringField(max_length=100)
    # Old pattern: Using deprecated primary_key option
    zip_code = StringField(primary_key=False)

# Old pattern: Using deprecated ReferenceField options
class Author(Document):
    """Author document."""
    name = StringField(required=True)
    email = StringField()

class Article(Document):
    """Old article pattern with deprecated reference options."""
    title = StringField(required=True)
    content = StringField()
    # Deprecated: Using deprecated ReferenceField parameters
    author = ReferenceField(
        Author,
        # Deprecated: Using dbref parameter
        dbref=False,
        # Old pattern: Using deprecated reverse_delete_rule
        reverse_delete_rule=2  # CASCADE - should use constant
    )
    # Old pattern: Using deprecated ListField with ReferenceField
    reviewers = ListField(
        ReferenceField(Author, dbref=True)  # Deprecated dbref
    )
    
    meta = {
        'collection': 'articles'
    }

# Old pattern: Using deprecated QuerySet methods
class OldQuerySetUsage:
    """Old QuerySet patterns."""
    
    @staticmethod
    def find_articles_old():
        """Old query patterns."""
        # Deprecated: Using .count() instead of len() or .count_documents()
        total = Article.objects.count()
        
        # Old pattern: Using deprecated exec_js
        # Deprecated: Using map_reduce
        
        # Old pattern: Using deprecated only/exclude with fields
        articles = Article.objects.only('title', 'content')
        
        # Deprecated: Using .first() with old behavior
        first_article = Article.objects.first()
        
        return articles
    
    @staticmethod
    def update_articles_old():
        """Old update patterns."""
        # Deprecated: Using deprecated update operators
        Article.objects(title='old').update(
            set__title='new',  # Old pattern
            # Deprecated: Using upsert in old way
            upsert=True
        )
        
        # Old pattern: Using deprecated modify method
        Article.objects(title='test').modify(
            set__content='updated',
            # Deprecated: Using new parameter
            new=True
        )
    
    @staticmethod
    def aggregate_old():
        """Old aggregation patterns."""
        # Deprecated: Using old aggregate syntax
        pipeline = [
            {'$match': {'title': {'$exists': True}}},
            {'$group': {'_id': '$author', 'count': {'$sum': 1}}}
        ]
        # Old pattern: Using deprecated aggregate method
        result = Article.objects.aggregate(*pipeline)
        return list(result)

# Old pattern: Using deprecated DynamicDocument features
class OldDynamicDoc(DynamicDocument):
    """Old dynamic document pattern."""
    name = StringField(required=True)
    
    meta = {
        # Deprecated: Using strict mode with DynamicDocument
        'strict': False,
        # Old pattern: Using deprecated max_documents
        'max_documents': 10000,
        # Deprecated: Using max_size
        'max_size': 1000000
    }

# Old pattern: Using deprecated signals
from mongoengine import signals

def handler(sender, document, **kwargs):
    """Old signal handler."""
    print(f"Document saved: {document}")

# Deprecated: Using old signal registration
signals.post_save.connect(handler, sender=Article)

# Old pattern: Using deprecated connection management
def get_db_old():
    """Old database access pattern."""
    # Deprecated: Using get_connection and get_db directly
    conn = get_connection()
    db = get_db()
    return db

# Old pattern: Using deprecated field options
class OldFieldOptions(Document):
    """Document with deprecated field options."""
    # Deprecated: Using unique_with
    name = StringField(unique_with='category')
    category = StringField()
    # Old pattern: Using deprecated choices format
    status = StringField(choices=['draft', 'published', 'archived'])
    # Deprecated: Using deprecated regex validator
    email = StringField(regex=r'^[\w.]+@[\w.]+\.\w+$')
