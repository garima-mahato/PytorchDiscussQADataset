import scrapy
import pandas as pd
from ast import literal_eval
import json

from bs4 import BeautifulSoup
from bs4.element import Comment


def tag_visible(element):
    if element.parent.name not in ['code']:
        return False
    if isinstance(element, Comment):
        return False
    return True


def text_from_html(body):
    soup = BeautifulSoup(body, 'html.parser')
    texts = soup.findAll(text=True)
    print(texts)
    visible_texts = filter(tag_visible, texts)
    print(visible_texts)
    return u" ".join(t.strip() for t in visible_texts)

class PytorchDiscussQASpider(scrapy.Spider):
    name = 'pytorch_discuss_qa'
    allowed_domains = ['pytorch.org']
    start_url = ['https://discuss.pytorch.org/']
    start_urls = ['https://discuss.pytorch.org/categories.json']

    def parse(self, response):
        res = json.loads(response.body.decode('utf8'))
        category_list = res["category_list"]["categories"] # response.css('table.category-list td.category')
        
        for item in category_list:
            anchor = self.start_url[0] + "c/" + item["slug"] + "/" + str(item["id"]) + ".json?page=1&solved=yes" # f"{self.start_urls[0].rstrip('/')}{item.css('h3 a::attr(href)').extract()[0]}.json?page=1&solved=yes"
            cat = item["slug"] #anchor.split('/')[-2]
            if cat not in ["site-feedback", "jobs"]:
                yield scrapy.Request(anchor, callback=self.parse_category_links, cb_kwargs=dict(category=cat))
                                    
    def parse_category_links(self, response, category):
        res = json.loads(response.body.decode('utf8'))
       
        df = pd.DataFrame(res["topic_list"]["topics"])
        if "id" in df.columns.values and "slug" in df.columns.values:
            df["link"] = df.apply(lambda r: self.start_url[0] + "t/" + r["slug"] + "/" + str(r["id"]), axis=1)
            links = df["link"].values # response.css('table.topic-list td.main-link a.title::attr(href)').extract()
            for link in links:
                yield scrapy.Request(link+'.json', callback=self.parse_category_link_page, cb_kwargs=dict(category=category, url=link))
                        
        if "more_topics_url" in res["topic_list"].keys():
            more_links = self.start_url[0].rstrip('/') + res["topic_list"]["more_topics_url"].split('?')[0] + ".json?" + res["topic_list"]["more_topics_url"].split('?')[1]
            yield scrapy.Request(more_links, callback=self.parse_category_links, cb_kwargs=dict(category=category))
        
    def parse_category_link_page(self, response, category, url):
        qas = {}
        res = json.loads(response.body.decode('utf8'))
        posts = res["post_stream"]["posts"]
        posts_df = pd.DataFrame(posts)
        qas["pytorch_discuss_id"] = posts[0]["id"]
        qas["source"] = "pytorch_discuss"
        qas["url"] = url
        qas["query"] = posts[0]["cooked"]
        qas["solution"] = posts_df[posts_df["accepted_answer"]==True]["cooked"].values[0]
        qas["solution_has_code"] = True if "</code>" in qas["solution"] else False
        qas["query_has_code"] = True if "</code>" in qas["query"] else False
        qas["category"] = category
        qas["intent"] = " ".join(posts[0]["topic_slug"].split("-"))

        yield qas