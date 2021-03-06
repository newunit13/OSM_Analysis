import csv
import pprint
import re
import xml.etree.cElementTree as ET

import cerberus

import schema

OSM_PATH = "raw_data/louisville_small.osm"

NODES_PATH     = "csv_data/nodes.csv"
NODE_TAGS_PATH = "csv_data/nodes_tags.csv"
WAYS_PATH      = "csv_data/ways.csv"
WAY_NODES_PATH = "csv_data/ways_nodes.csv"
WAY_TAGS_PATH  = "csv_data/ways_tags.csv"

LOWER_COLON = re.compile(r'^([a-z]|_)+:([a-z]|_)+')
PROBLEMCHARS = re.compile(r'[=\+/&<>;\'"\?%#$@\,\. \t\r\n]')

SCHEMA = schema.schema

# Make sure the fields order in the csvs matches the column order in the sql table schema
NODE_FIELDS      = ['id', 'lat', 'lon', 'user', 'uid', 'version', 'changeset', 'timestamp']
NODE_TAGS_FIELDS = ['id', 'key', 'value', 'type']
WAY_FIELDS       = ['id', 'user', 'uid', 'version', 'changeset', 'timestamp']
WAY_TAGS_FIELDS  = ['id', 'key', 'value', 'type']
WAY_NODES_FIELDS = ['id', 'node_id', 'position']


def shape_element(element, node_attr_fields=NODE_FIELDS, way_attr_fields=WAY_FIELDS,
                  problem_chars=PROBLEMCHARS, default_tag_type='regular'):
    """Clean and shape node or way XML element to Python dict"""

    node_attribs = {}
    way_attribs = {}
    way_nodes = []
    tags = []

    
    node_element = element.tag == 'node'
    way_element = element.tag == 'way'
    
    if node_element:
        node_attribs = {field:element.attrib[field] for field in node_attr_fields}
    elif way_element:
        way_attribs = {field:element.attrib[field] for field in way_attr_fields}
        for idx, nd in enumerate(element.iter('nd')):
            way_node = {'id': element.attrib['id'],
                        'node_id': nd.attrib['ref'],
                        'position': idx,
                       }
            
            way_nodes.append(way_node)
    
    for tag in element.iter("tag"):
        
        tag_key = tag.attrib["k"]
        tag_value = tag.attrib["v"]
        
        if problem_chars.match(tag_key):
            continue
        
        try:
            tag_type, tag_key = tag_key.split(':', 1)
        except ValueError:
            tag_type = default_tag_type
        
        tag = {'id': element.attrib['id'],
               'key': tag_key,
               'value': tag_value,
               'type': tag_type,
              }
        
        tags.append(tag)
    

    if element.tag == 'node':
        return {'node': node_attribs, 'node_tags': tags}
    elif element.tag == 'way':
        return {'way': way_attribs, 'way_nodes': way_nodes, 'way_tags': tags}


# ================================================== #
#               Helper Functions                     #
# ================================================== #
def get_element(osm_file, tags=('node', 'way', 'relation')):
    """Yield element if it is the right type of tag"""

    context = ET.iterparse(osm_file, events=('start', 'end'))
    _, root = next(context)
    for event, elem in context:
        if event == 'end' and elem.tag in tags:
            yield elem
            root.clear()


def validate_element(element, validator, schema=SCHEMA):
    """Raise ValidationError if element does not match schema"""
    if validator.validate(element, schema) is not True:
        field, errors = next(validator.errors.iteritems())
        message_string = "\nElement of type '{0}' has the following errors:\n{1}"
        error_string = pprint.pformat(errors)
        
        raise Exception(message_string.format(field, error_string))

# ================================================== #
#               Main Function                        #
# ================================================== #
def process_map(file_in, validate):
    """Iteratively process each XML element and write to csv(s)"""

    with open(NODES_PATH, 'w') as nodes_file, \
         open(NODE_TAGS_PATH, 'w') as nodes_tags_file, \
         open(WAYS_PATH, 'w') as ways_file, \
         open(WAY_NODES_PATH, 'w') as way_nodes_file, \
         open(WAY_TAGS_PATH, 'w') as way_tags_file:

        nodes_writer     = csv.DictWriter(nodes_file, NODE_FIELDS, lineterminator='\n')
        node_tags_writer = csv.DictWriter(nodes_tags_file, NODE_TAGS_FIELDS, lineterminator='\n')
        ways_writer      = csv.DictWriter(ways_file, WAY_FIELDS, lineterminator='\n')
        way_nodes_writer = csv.DictWriter(way_nodes_file, WAY_NODES_FIELDS, lineterminator='\n')
        way_tags_writer  = csv.DictWriter(way_tags_file, WAY_TAGS_FIELDS, lineterminator='\n')

        nodes_writer.writeheader()
        node_tags_writer.writeheader()
        ways_writer.writeheader()
        way_nodes_writer.writeheader()
        way_tags_writer.writeheader()

        validator = cerberus.Validator()

        for element in get_element(file_in, tags=('node', 'way')):
            el = shape_element(element)
            if el:
                if validate is True:
                    validate_element(el, validator)

                if element.tag == 'node':
                    nodes_writer.writerow(el['node'])
                    for row in el['node_tags']:
                        node_tags_writer.writerow(row)
                elif element.tag == 'way':
                    ways_writer.writerow(el['way'])
                    way_nodes_writer.writerows(el['way_nodes'])
                    way_tags_writer.writerows(el['way_tags'])


if __name__ == '__main__':
    # Note: Validation is ~ 10X slower. For the project consider using a small
    # sample of the map when validating.
    process_map(OSM_PATH, validate=False)
    print("Finished")
