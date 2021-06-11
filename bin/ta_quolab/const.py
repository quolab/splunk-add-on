
quolab_classes = {
    'fact': [
        'autonomous-system',
        'certificate',
        'domain',
        'email',
        'envelope',
        'file',
        'function',
        'hostname',
        'import-table',
        'ip-address',
        'mutex',
        'process',
        'registry-key',
        'url',
        'wallet',
        'export-table',
        'malware',
        'blob',
        'ttp',
        'organization',
        'persona',
        'region',
        'tor-descriptor',
        'transaction',
        'yara-rule',
    ],
    'reference': [
        'accesses',
        'contains',
        'creates',
        'identified-as',
        'loads',
        'matches',
        'relates-to',
        'signed-by',
        'receives-from',
        'sends-to',
        'delivered',
        'resolved-to',
    ],
    'annotation': [
        'attribute',
        'text',
        'interpreted-as',
        'known-as',
        'geodata',
        'report',
    ],
    'sysfact': [
        'case',
        'resource',
        'script',
        'tag',
        'timeline',
        'text',
        'user',
        'group',
        'subscription',
        'connector',
        'regulator',
        'endpoint',
    ],
    'sysref': [
        'queued',
        'scheduled',
        'executed',
        'canceled',
        'failed',
        'observed-by',
        'commented-by',
        'monitors',
        'associated-with',
        'encases',
        'tagged',
        'uses',
        'synchronized-with',
        'implies',
        'authorizes',
        'member-of',
        'produced',
    ]
}


facets = [
    'cases',
    'contributors',
    'document.magic',
    'commented',
    'document',
    'sources',
    'producers',
    'refcount',
    'vault-stored',
    'display',
    'actions',
    'endpoints',
    'latest-internal-observation',
    'tagged',
]

quolab_types = set()
quolab_class_from_type = {}

resolve_override = {
    "text": "sysfact",
}


def init():
    for class_, types in quolab_classes.items():
        for type_ in types:
            if type_ in quolab_types:
                if type_ in resolve_override:
                    class_ = resolve_override[type_]
                else:
                    # XXX: This assertion would be better as a unittest
                    raise AssertionError("Duplicate entry for {}:  {} vs {}".format(
                        type_, quolab_class_from_type[type_], class_))
            quolab_types.add(type_)
            quolab_class_from_type[type_] = class_


init()
