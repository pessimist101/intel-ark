import discord
from discord.ext import commands
import aiohttp
import asyncio
import bs4
from bs4 import BeautifulSoup as soup
import urllib.parse
import re

desiredSpecs = ('ProcessorNumber','CoreCount','ThreadCount','HyperThreading','ClockSpeed','SocketsSupported','MaxTDP','AESTech','MaxMem')

class IntelArk(commands.Cog):
    """Search for Intel CPUs"""

    def __init__(self, client):
        self.client = client
        self.intelBlue = 0x0071C5
        self.specialQueries = {
        "@everyone": "Hah. Nice try. Being very funny. Cheeky cunt.",
        "@here": "Hilarious, I'm reporting you to the mods.",
        ":(){ :|: & };: -": "This is a python bot, not a bash bot you nimwit."
        }
        self.headers = {'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/80.0.3987.163 Safari/537.36'}

    # Events
    @commands.Cog.listener()
    async def on_ready(self):
        print('Intel Ark cog online')

    @commands.command()
    async def ark(self, ctx, *searchTerm):
        """Search for Intel CPUs"""
        for word in searchTerm:
            if word in self.specialQueries:
                await ctx.send(embed=discord.Embed(colour=self.intelBlue,description=self.specialQueries[word]))
                return
            if re.compile('<@![0-9]{18}>').match(word):
                await ctx.send(embed=discord.Embed(colour=self.intelBlue,description=f"<@{ctx.author.id}> pong!"))
                return

        indexModifier = re.compile('r=[0-9]')
        if indexModifier.match(searchTerm[-1]):
            regexMatched = True
            matchedString = searchTerm[-1]
            searchTerm = " ".join(searchTerm[:-1])
        else:
            regexMatched = False
            searchTerm = " ".join(searchTerm)
        cleanSearchTerm = urllib.parse.quote(searchTerm) # clean up the search term for the url

        data = await self.get_urls(cleanSearchTerm)
        if data is None: # If no results
            embed = discord.Embed(colour=self.intelBlue,description=f"No results found for `{searchTerm.replace('`','``')}`")
            await ctx.send(embed=embed)
            return
        if type(data) is dict and data.keys() == desiredSpecs: # If only one result
            index = {'min':0,'current':0,'max':0}
            embed = await self.make_ark_embed(data,index)
            await ctx.send(embed=embed)
            return
        elif type(data) is list: # If multiple results
            index = {'min':0,'max':len(data)-1}
            if regexMatched == True:
                newIndex = int(matchedString.split('r=')[1])
                index['current'] = newIndex * -1 if newIndex < 0 else newIndex
                index['current'] = index['max'] if index['current'] > index['max'] else index['current']
            else:
                index['current'] = 0
        cpuData = await self.get_cpu_data(data[index['current']])
        arkEmbed = await self.make_ark_embed(cpuData,index)
        messageObject = await ctx.send(embed=arkEmbed)
        allowedEmojis = await self.add_buttons(messageObject, index)

        def reaction_info_check(reaction,user):
            return user == ctx.author and reaction.message.id == messageObject.id and reaction.emoji in allowedEmojis

        try:
            reaction, user = await self.client.wait_for('reaction_add', timeout=180.0, check=reaction_info_check)
        except asyncio.TimeoutError:
            await messageObject.clear_reactions()
            return
        else:
            # Okay, the user has reacted with an emoji, let's find out which one!
            if reaction.emoji == '▶':
                index['current'] +=  1
                await self.editResult(ctx, data,index,messageObject)
            if reaction.emoji == '◀':
                index['current'] -= 1
                await self.editResult(ctx, data,index,messageObject)

    async def editResult(self, ctx, urls, index, messageObject):
        data = await self.get_cpu_data(urls[index['current']])
        embed = await self.make_ark_embed(data,index)
        await messageObject.edit(embed=embed)
        allowedEmojis = await self.add_buttons(messageObject,index)
        def reaction_info_check(reaction,user):
            return user == ctx.author and reaction.message.id == messageObject.id and reaction.emoji in allowedEmojis

        try:
            reaction, user = await self.client.wait_for('reaction_add', timeout=120.0, check=reaction_info_check)
        except asyncio.TimeoutError:
            await messageObject.clear_reactions()
            return
        else:
            # Okay, the user has reacted with an emoji, let's find out which one!
            if reaction.emoji == '▶':
                index['current'] += 1
                await self.editResult(ctx, urls,index,messageObject)
            if reaction.emoji == '◀':
                index['current'] -= 1
                await self.editResult(ctx, urls,index,messageObject)

    async def get_urls(self, searchTerm):
        url = f"https://ark.intel.com/content/www/us/en/ark/search.html?_charset_=UTF-8&q={searchTerm}"
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=self.headers, allow_redirects=True) as data:
                dataText = await data.text()
                page_soup = soup(dataText, "html.parser")
                await session.close()

        if (page_soup.find("input",{"id":"FormRedirectUrl"})): # if only one result
            url = page_soup.find("input",{"id":"FormRedirectUrl"}).get('value')
            url = f"https://ark.intel.com{url}"
            data = await self.get_cpu_data(url)
            return data
        if (page_soup.find("h2",text="No products matching your request were found.")): # if no products found
            embed = discord.Embed(colour=self.intelBlue,description=f"No results found for `{searchTerm.replace('`','``')}`")
            await ctx.send(embed=embed)
            return None
        # build list of URLs
        results = page_soup.findAll("div",{"class":"search-result"})
        urls = []
        ignore = ['generation','ethernet','wireless','products formerly','heat sink']
        for item in results:
            trigger = 0
            itemTitle = item.find("h4",{"class":"result-title"}).find("a").contents[0].strip().lower()
            for word in ignore:
                if word in itemTitle:
                    trigger = 1
                    break
            if trigger == 1:
                continue
            else:
                url = item.find("h4",{"class":"result-title"}).find("a").get('href')
                url = f"https://ark.intel.com{url}"
                urls.append(url)
        return urls

    async def get_cpu_data(self, url):
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=self.headers) as data:
                dataText = await data.text()
                page_soup = soup(dataText, "html.parser")
                await session.close()
        specs = {}
        specs['Url'] = url
        for specItem in desiredSpecs:
            try:
                specs[specItem] = page_soup.find("span",{"class":"value","data-key":specItem}).contents[0].strip()
            except AttributeError:
                specs[specItem] = None
        try:
            specs['VTD'] = page_soup.find("span",{"class":"value","data-key":"VTD"}).contents[0].strip()
        except AttributeError:
            specs['VTD'] = None
        try:
            specs['ClockSpeedMax'] = page_soup.find("span",{"class":"value","data-key":"ClockSpeedMax"}).contents[0].strip()
        except AttributeError: # If the CPU doesn't have a boost frequency
            specs['ClockSpeedMax'] = None
        return specs

    async def make_ark_embed(self, data, index):
        embed = discord.Embed(colour=self.intelBlue)
        embed.set_author(name='Ark Search Result',url=data['Url'])
        embed.add_field(name='Product Name',value=f"[{data['ProcessorNumber']}]({data['Url']})",inline=True)
        if data['ClockSpeed'] != None:
            if data['ClockSpeedMax'] != None:
                embed.add_field(name='Clock Speed',value=f"{data['ClockSpeed']} / {data['ClockSpeedMax']}",inline=True)
            else:
                embed.add_field(name='Clock Speed',value=data['ClockSpeed'],inline=True)
        cTValue = f"{data['CoreCount']} / {data['CoreCount']}" if data['HyperThreading'] == 'No' or data['HyperThreading'] == None else f"{data['CoreCount']} / {data['ThreadCount']}"
        embed.add_field(name='Cores/Threads',value=cTValue,inline=True)
        if data['MaxTDP'] != None:
            embed.add_field(name='TDP',value=data['MaxTDP'],inline=True)
        if data['VTD'] != None:
            embed.add_field(name='VTD',value=data['VTD'],inline=True)
        if data['AESTech'] != None:
            embed.add_field(name='AES Tech',value=data['AESTech'],inline=True)
        if data['SocketsSupported'] != None:
            embed.add_field(name='Sockets',value=data['SocketsSupported'],inline=True)
            embed.set_footer(text=f"{index['current']+1} of {index['max']}")
        return embed

    async def add_buttons(self, messageObject, index):
        messageObject = await messageObject.channel.fetch_message(messageObject.id)
        oldReacts = [i.emoji for i in messageObject.reactions if i.me]
        if index['current'] == index['min']: # first result, no back arrow required
            allowedEmojis = ['▶']
        if index['current'] == index['max']: # last result, no forward arrow required
            allowedEmojis = ['◀']
        if index['min'] < index['current'] < index['max']: # a middle result, both arrows required
            allowedEmojis = ['◀','▶']
        if oldReacts == allowedEmojis:
            for reaction in [i for i in messageObject.reactions if not reaction.me]:
                await messageObject.remove_reaction(reaction.emoji,ctx.author)
        else:
            await messageObject.clear_reactions()
            for emoji in allowedEmojis:
                await messageObject.add_reaction(emoji)
        return allowedEmojis


def setup(client):
    client.add_cog(IntelArk(client))
