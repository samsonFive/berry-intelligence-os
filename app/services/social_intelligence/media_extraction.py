"""Literal multimedia proposal boundary, no unqualified model/tool execution."""
import re

FIELDS=('brand','product','variety','retailer','price','currency','weight','barcode','origin','grower','distributor','claim')
def label_fields(literal):
    """Reviewable labeled OCR/human text, never visual cultivar inference."""
    result=[]
    text=literal['text']
    for m in re.finditer(r'(?im)\b('+ '|'.join(FIELDS) +r')\s*:\s*([^\n;]+)',text):
        result.append({'field':m.group(1).lower(),'literal':m.group(2).strip(),
                       'locator':literal['locator'],'method':literal['method'],'version':literal['version'],
                       'confidence':literal['confidence'],'review':'proposed'})
    return result

def media_observations(item):
    return [{'media_id':m['id'],'parent_native_id':m['parent_native_id'],'state':m['state'],
             'fields':[field for lit in m['literal'] for field in label_fields(lit)] if m['state']=='available' else [],
             'analysis_status':'literal text supplied; no automatic OCR/vision provider configured' if m['literal'] else 'unsupported / no extraction',
             'does_not_prove':'Appearance does not identify cultivar, diagnose condition or establish food safety'} for m in item['media']]
