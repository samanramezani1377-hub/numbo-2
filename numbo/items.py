import scrapy

class ContactItem(scrapy.Item):
    source_url = scrapy.Field()
    domain = scrapy.Field()
    title = scrapy.Field()
    phones = scrapy.Field()
    emails = scrapy.Field()
    address = scrapy.Field()
    business_name = scrapy.Field()
    category = scrapy.Field()
    city = scrapy.Field()
    socials = scrapy.Field()
    technologies = scrapy.Field()
    crawled_at = scrapy.Field()
    quality_score = scrapy.Field()
    evidence = scrapy.Field()
