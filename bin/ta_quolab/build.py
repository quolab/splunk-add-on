
import sys
import json

from .const import quolab_classes, facets


def build_searchbnf(stream=sys.stdout):
    """
    >>> import quolab_query
    >>> quolab_query.build_searchbnf()
    """
    stream.write("[quolab-types]\n")
    types = []
    # Don't bother showing reference/sysref in the UI docs (to keep the list
    # from becoming too long and unreadable)
    for class_ in ["sysfact", "fact", "annotation"]:
        types.extend(quolab_classes[class_])
    stream.write("syntax = ({})\n".format("|".join(types)))

    stream.write("[quolab-facets]\n")
    stream.write("syntax = ({})\n".format("|".join(sorted(facets))))


def build_facets(data):
    """ Data from facets-serves.json

    Data structure:
    { "services" : [
        {"(type)": "quolab...ClassName",
        "id": "<name>"}
     ] }
    """
    deprecated = {"casetree", "cache-id", "indirect"}
    services = [service["id"] for service in data["services"]
                if service["id"] not in deprecated]
    return services


def build_types(data):
    """ Extract datetypes from model-types.json
    API:    /v1/catalog/model/types

    Data Structure:
    { "types: {
        "<class>: [
            {"type": "<type>"}
        ]
    }}

    data = json.load(open("model-types.json"))
    build_types(data)
    """
    deprecated = {"ipynb", "misp-blob", "source", "sink", "task", "sighted-by"}
    qlc = {}
    for class_, types in data["types"].items():
        type_names = [t["type"] for t in types if t["type"] not in deprecated]
        qlc[class_] = type_names
    # print(repr(qlc))
    return qlc


def build_from_json(output=sys.stdout):
    # TODO:  Make list output show up on the following line.   Something like:  replace(": ['", ": [\n    '").  Maybe just use json dump?
    from pprint import pprint
    pp_args = {
        "compact": False
    }
    if sys.version_info > (3, 8):
        pp_args["sort_dicts"] = False
    data = json.load(open("model-types.json"))
    qlc = build_types(data)
    output.write("quolab_classes = ")
    pprint(qlc, stream=output, **pp_args)
    output.write("\n\n")

    data = json.load(open("facet-services.json"))
    facets = build_facets(data)
    output.write("facets = ")
    pprint(facets, stream=output, **pp_args)
    output.write("\n\n")
