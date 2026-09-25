import scrapy


class ContactItem(scrapy.Item):
    source_url = scrapy.Field()
    domain = scrapy.Field()
    title = scrapy.Field()
    phones = scrapy.Field()          # list of normalized phones
    emails = scrapy.Field()          # list of emails
    address = scrapy.Field()
    business_name = scrapy.Field()
    category = scrapy.Field()
    city = scrapy.Field()
    socials = scrapy.Field()         # dict of platform -> url
    technologies = scrapy.Field()    # list of {name, confidence, evidence}
    crawled_at = scrapy.Field()
