"""
Old Elasticsearch patterns that need migration.
Uses deprecated patterns from elasticsearch-py 7.x that changed in 8.x+
"""
from elasticsearch import Elasticsearch, helpers
from elasticsearch.exceptions import NotFoundError, ConflictError

# Old pattern: Using deprecated connection parameters
es = Elasticsearch(
    ['localhost:9200'],
    # Deprecated: Using scheme and port separately
    scheme='http',
    port=9200,
    # Old pattern: Using deprecated http_auth tuple
    http_auth=('elastic', 'password'),
    # Deprecated: Using use_ssl parameter
    use_ssl=False,
    # Deprecated: Using verify_certs parameter
    verify_certs=False,
    # Old pattern: Using deprecated timeout parameter
    timeout=30,
    # Deprecated: Using max_retries
    max_retries=3,
    # Old pattern: Using deprecated retry_on_timeout
    retry_on_timeout=True
)

# Old pattern: Using deprecated index/doc_type structure
def index_document_old(index, doc_type, doc_id, body):
    """Old indexing pattern with doc_type (removed in ES 8.x)."""
    # Deprecated: Using doc_type parameter
    result = es.index(
        index=index,
        doc_type=doc_type,  # Deprecated: doc_type removed in ES 8.x
        id=doc_id,
        body=body,  # Deprecated: use document parameter
        # Old pattern: Using deprecated refresh parameter value
        refresh='wait_for'
    )
    return result

# Old pattern: Using deprecated search body syntax
def search_documents_old(index, query_string):
    """Old search pattern with body parameter."""
    # Deprecated: Using body parameter instead of query parameter
    result = es.search(
        index=index,
        # Deprecated: Using body dict
        body={
            'query': {
                'match': {
                    'content': query_string
                }
            },
            # Old pattern: Using deprecated fields parameter
            'fields': ['title', 'content'],
            # Deprecated: Using _source parameter in body
            '_source': True,
            # Old pattern: Using deprecated size/from
            'size': 10,
            'from': 0
        }
    )
    return result['hits']['hits']

# Old pattern: Using deprecated update syntax
def update_document_old(index, doc_type, doc_id, fields):
    """Old update pattern."""
    # Deprecated: Using doc_type and body parameters
    result = es.update(
        index=index,
        doc_type=doc_type,  # Deprecated
        id=doc_id,
        body={  # Deprecated: use doc parameter
            'doc': fields
        },
        # Deprecated: Using retry_on_conflict parameter
        retry_on_conflict=3
    )
    return result

# Old pattern: Using deprecated delete syntax
def delete_document_old(index, doc_type, doc_id):
    """Old delete pattern."""
    try:
        # Deprecated: Using doc_type parameter
        es.delete(
            index=index,
            doc_type=doc_type,  # Deprecated
            id=doc_id,
            # Old pattern: Using deprecated refresh parameter
            refresh=True
        )
    except NotFoundError:
        pass

# Old pattern: Using deprecated bulk helper syntax
def bulk_index_old(index, doc_type, documents):
    """Old bulk indexing pattern."""
    actions = []
    for doc in documents:
        actions.append({
            '_index': index,
            '_type': doc_type,  # Deprecated: _type removed
            '_id': doc.get('id'),
            '_source': doc
        })
    
    # Deprecated: Using old bulk parameters
    success, failed = helpers.bulk(
        es,
        actions,
        # Deprecated: Using old parameters
        chunk_size=500,
        raise_on_error=False,
        raise_on_exception=False
    )
    return success, failed

# Old pattern: Using deprecated scan helper
def scan_all_documents_old(index, doc_type, query):
    """Old scan helper pattern."""
    # Deprecated: Using doc_type and preserve_order parameters
    for doc in helpers.scan(
        es,
        index=index,
        doc_type=doc_type,  # Deprecated
        query=query,
        # Deprecated: Using scroll parameter with old format
        scroll='5m',
        # Old pattern: Using preserve_order
        preserve_order=True,
        # Deprecated: Using size parameter
        size=1000
    ):
        yield doc

# Old pattern: Using deprecated indices client methods
def manage_index_old(index):
    """Old index management patterns."""
    # Deprecated: Using body parameter for mappings
    es.indices.create(
        index=index,
        body={  # Deprecated: use mappings and settings parameters
            'settings': {
                'number_of_shards': 1,
                'number_of_replicas': 0
            },
            'mappings': {
                # Deprecated: Using doc_type in mappings
                '_doc': {
                    'properties': {
                        'title': {'type': 'text'},
                        'content': {'type': 'text'}
                    }
                }
            }
        }
    )

# Old pattern: Using deprecated get syntax
def get_document_old(index, doc_type, doc_id):
    """Old get document pattern."""
    try:
        # Deprecated: Using doc_type and _source_include
        result = es.get(
            index=index,
            doc_type=doc_type,  # Deprecated
            id=doc_id,
            _source_includes=['title', 'content'],  # Old parameter name
            _source_excludes=['internal_field']
        )
        return result['_source']
    except NotFoundError:
        return None

# Old pattern: Using deprecated mget syntax
def multi_get_old(index, doc_type, ids):
    """Old multi-get pattern."""
    # Deprecated: Using body parameter
    result = es.mget(
        index=index,
        doc_type=doc_type,  # Deprecated
        body={  # Deprecated: use docs parameter
            'ids': ids
        }
    )
    return result['docs']
