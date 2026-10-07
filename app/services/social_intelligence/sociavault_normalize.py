"""Inspectable field mappings; no query-language/geography or avatar inference."""
from datetime import datetime,timezone
from email.utils import parsedate_to_datetime
from html import unescape
from html.parser import HTMLParser
import re
from urllib.parse import urlsplit,parse_qs
from .adapters import common,AccessBlocked
from .model import validate_intake,safe_url

def values(value):
    return list(value.values()) if isinstance(value,dict) else value if isinstance(value,list) else []

def timestamp(value):
    if not value:return None
    try:
        if isinstance(value,(int,float)):return datetime.fromtimestamp(value,timezone.utc).isoformat()
        try:d=datetime.fromisoformat(str(value).replace('Z','+00:00'))
        except ValueError:d=parsedate_to_datetime(str(value))
        return d.astimezone(timezone.utc).isoformat() if d.tzinfo else None
    except (ValueError,TypeError,OverflowError):return None

def media(row,url,kind='image'):
    if not isinstance(url,str) or not url.startswith('https://'):return
    url=unescape(url)
    try:safe_url(url)
    except ValueError:return
    if any(m['source_url']==url for m in row['media']):return
    row['media'].append({'id':row['native_id'][:150]+f'-{kind}-{len(row["media"])}',
      'parent_native_id':row['native_id'],'kind':kind,'source_url':url,'mime':kind+'/reference',
      'state':'available','storage_permission':'reference_only','attribution':'Original '+row['source']+' media reference via SociaVault',
      'retention':'Reference only; URL availability and redisplay rights not independently verified; no rehosting'})

def _row(platform,native,url,text,published,language='und',parent=None):
    if not native or not url:raise ValueError('Native ID and attributable source URL required')
    row=common(platform,str(native),safe_url(url),unescape(str(text or ''))[:20000],language or 'und',timestamp(published),parent)
    row.update(discovery_method='sociavault-bounded-pilot',query_version='sociavault-multiplatform-2026-10-07-v1',
      permission_basis='Private provider evaluation; public source references; no storage/redistribution rights inferred',
      attribution='Original '+platform+' source via SociaVault')
    return row

def _tweets(data):
    found=[]
    def walk(node):
        if isinstance(node,dict):
            if node.get('__typename')=='Tweet' and node.get('rest_id') and 'legacy' in node:
                found.append(node);return # do not promote quoted/retweeted subtrees as new originals
            for key,value in node.items():
                if key not in ('user_results','quoted_status_result','retweeted_status_result'):walk(value)
        elif isinstance(node,list):
            for value in node:walk(value)
    walk(data.get('result',{}))
    return found

class CommentImages(HTMLParser):
    """Read URLs only; never render or execute untrusted comment HTML."""
    def __init__(self):super().__init__();self.urls=[]
    def handle_starttag(self,tag,attrs):
        if tag=='img':
            src=dict(attrs).get('src')
            if src:self.urls.append(src)

def _reddit_comments(items):
    result=[]
    def walk(entries,depth=0):
        if depth>6:return
        for post in values(entries):
            if len(result)>=200:return
            if not isinstance(post,dict):continue
            post=post.get('data',post);result.append(post)
            replies=post.get('replies') or {}
            if isinstance(replies,dict):walk(replies.get('items') or replies.get('data',{}).get('children') or [],depth+1)
            elif isinstance(replies,list):walk(replies,depth+1)
    walk(items)
    return result

def normalize(payload,task,*,supplied_url=None,supplied_parent_id=None):
    data=payload.get('data',payload)
    if not payload.get('success') or not isinstance(data,dict) or data.get('success') is False or data.get('error') or data.get('status_code',0)!=0:
        raise AccessBlocked('Unsuccessful nested provider response')
    platform=task.split('-')[0];errors=[];rows=[]
    comments=task.endswith('-comments')
    field={'reddit':'comments' if comments else 'posts','instagram':'comments' if comments else 'posts',
           'tiktok':'comments' if comments else 'search_item_list','linkedin':'posts','pinterest':'pins'}.get(platform)
    if platform=='x':items=_tweets(data)
    elif platform=='youtube':items=values(data.get('comments')) if comments else sum((values(data.get(k)) for k in ('videos','shorts','lives')),[])
    elif task=='instagram-post':items=[data.get('xdt_shortcode_media') or data.get('data',{}).get('xdt_shortcode_media',{})]
    elif platform=='facebook':items=values(data.get('posts'))
    else:
        if field not in data:raise AccessBlocked('Unrecognized platform schema; not zero volume')
        items=values(data[field])
    raw_count=len(items)
    if platform=='reddit' and comments:
        items=_reddit_comments(items);raw_count=len(items)
    for item in items[:20 if comments else 10]:
        try:
            if platform=='reddit':
                post=item.get('data',item);native=post.get('name') or ('t1_' if comments else 't3_')+str(post.get('id') or '')
                if not post.get('id') and not post.get('name'):raise ValueError('Native identity absent')
                permalink=post.get('permalink');url='https://www.reddit.com'+permalink if permalink and permalink.startswith('/') else permalink or post.get('url')
                if comments and not url and supplied_url:url=supplied_url.rstrip('/')+'/'+str(post.get('id',''))+'/'
                text=post.get('body','') if comments else '\n'.join(filter(None,[post.get('title'),post.get('selftext')]))
                row=_row(platform,native,url,text,post.get('created_at_iso') or post.get('created_utc'),parent=(post.get('parent_id') or supplied_parent_id) if comments else None)
                for image in values(post.get('preview',{}).get('images')):media(row,image.get('source',{}).get('url'))
                for attached in values(post.get('media_metadata')):media(row,attached.get('s',{}).get('u'))
                if comments:
                    parsed=CommentImages();parsed.feed(unescape(post.get('body_html') or '')[:100000])
                    for url in parsed.urls[:30]:media(row,url)
                media(row,post.get('thumbnail'),'thumbnail')
                row['engagement']={k:v for k,v in {'likes':post.get('ups'),'comments':post.get('num_comments')}.items() if isinstance(v,int) and v>=0}
            elif platform=='tiktok':
                post=item if comments else item.get('aweme_info',item)
                native=post.get('cid' if comments else 'aweme_id');parent=str(post.get('reply_id') or post.get('aweme_id') or '') if comments else None
                if parent=='0':parent=str(post.get('aweme_id') or supplied_parent_id or '')
                url=supplied_url+'?comment_id='+str(native) if comments and supplied_url else post.get('url') or post.get('share_url')
                if not url and post.get('author',{}).get('unique_id'):
                    url=f'https://www.tiktok.com/@{post["author"]["unique_id"]}/video/{native}'
                row=_row(platform,native,url,post.get('text' if comments else 'desc'),post.get('create_time'),
                         post.get('comment_language' if comments else 'desc_language','und'),parent)
                for image in values(post.get('image_list')):
                    refs=values(image.get('url_list',[])) or values(image.get('display_image',{}).get('url_list',[]))
                    if refs:media(row,refs[0])
                cover=values(post.get('video',{}).get('cover',{}).get('url_list',[]))
                if cover:media(row,cover[0],'thumbnail')
                stats=post.get('statistics',{}) if not comments else {'digg_count':post.get('digg_count')}
                row['engagement']={k:v for k,v in stats.items() if isinstance(v,int) and v>=0}
            elif platform=='instagram':
                post=item;native=post.get('id') or post.get('pk');url=post.get('url')
                if comments and supplied_url:url=supplied_url+'?comment_id='+str(native)
                if not url and post.get('shortcode'):url='https://www.instagram.com/p/'+post['shortcode']+'/'
                if not url and task=='instagram-post':url=supplied_url
                caption=post.get('caption');text=caption.get('text') if isinstance(caption,dict) else caption
                if task=='instagram-post':
                    edges=values(post.get('edge_media_to_caption',{}).get('edges'));text=edges[0].get('node',{}).get('text','') if edges else text
                parent=supplied_parent_id if comments else None
                if comments and not parent:raise ValueError('Actual native parent ID required; shortcode is not numeric post ID')
                row=_row(platform,native,url,post.get('text') if comments else text,post.get('created_at') or post.get('taken_at') or post.get('taken_at_timestamp'),parent=parent)
                media(row,post.get('display_url') or post.get('thumbnail_src'),'thumbnail' if post.get('is_video') else 'image')
                for child in values(post.get('edge_sidecar_to_children',{}).get('edges')):media(row,child.get('node',{}).get('display_url'))
                row['engagement']={k:v for k,v in {'likes':post.get('like_count'),'comments':post.get('comment_count')}.items() if isinstance(v,int) and v>=0}
                if post.get('is_paid_partnership'):row['content_role']='disclosed_sponsorship'
            elif platform=='x':
                native=item['rest_id'];post=item['legacy'];parent=post.get('in_reply_to_status_id_str')
                row=_row(platform,native,'https://x.com/i/status/'+native,post.get('full_text'),post.get('created_at'),post.get('lang','und'),parent)
                for image in values(post.get('extended_entities',post.get('entities',{})).get('media')):
                    media(row,image.get('media_url_https'),'image' if image.get('type')=='photo' else 'thumbnail')
                row['engagement']={k:v for k,v in post.items() if k in ('favorite_count','reply_count','retweet_count') and isinstance(v,int) and v>=0}
            elif platform=='youtube':
                native=(item.get('commentId') or item.get('id')) if comments else item.get('id');url=item.get('url')
                if not url and native and not comments:url='https://www.youtube.com/watch?v='+str(native)
                if comments and supplied_url:url=supplied_url+'&lc='+str(native);parent=supplied_parent_id or parse_qs(urlsplit(supplied_url).query).get('v',[None])[0]
                else:parent=None
                row=_row(platform,native,url,(item.get('text') or item.get('content')) if comments else item.get('title'),item.get('publishedTime') or item.get('published_at'),parent=parent)
                for thumb in values(item.get('thumbnails')):media(row,thumb.get('url') if isinstance(thumb,dict) else thumb,'thumbnail')
                if not comments:media(row,item.get('thumbnail'),'thumbnail')
            elif platform=='linkedin':
                url=item.get('url');match=re.search(r'(?:activity-|urn:li:activity:)(\d+)',url or '')
                if not match:raise ValueError('Stable native LinkedIn activity ID absent')
                row=_row(platform,match.group(1),url,item.get('description') or item.get('name'),item.get('datePublished'))
                media(row,item.get('image'))
                for image in values(item.get('images')):media(row,image.get('url') if isinstance(image,dict) else image)
            elif platform=='pinterest':
                row=_row(platform,item.get('id'),item.get('url'),'\n'.join(filter(None,[item.get('title'),item.get('description')])),item.get('created_at'))
                images=item.get('images',{});image=images.get('orig') or images.get('736x') or images.get('474x') or {}
                media(row,image.get('url'))
            elif platform=='facebook':
                row=_row(platform,item.get('id'),item.get('url'),item.get('text'),item.get('publishTime'))
                media(row,item.get('image'));media(row,item.get('videoDetails',{}).get('thumbnailUrl'),'thumbnail')
            else:raise ValueError('Mapping not implemented')
            rows.append(validate_intake(row))
        except (ValueError,TypeError,KeyError) as exc:
            errors.append(type(exc).__name__) # no raw bodies or sensitive fields in report
    return {'rows':rows,'returned_items':raw_count,'mapped_items':len(rows),'mapping_errors':errors,
            'client_cap':20 if comments else 10}
