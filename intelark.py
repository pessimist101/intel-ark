"""Cog for searching the Intel Ark website"""
import discord
from discord.ext import commands, tasks
import aiohttp
import asyncio
import bs4
from bs4 import BeautifulSoup as soup
import urllib.parse
import re

class IntelArk(commands.Cog):

    def __init__(self, client):
        self.client = client
        self.intelBlue = 0x0071C5
        self.specialQueries = {
        '@everyone': "Hah. Nice try. Being very funny. Cheeky cunt.",
        ':(){ :|: & };: -': "This is a python bot, not a bash bot you nimwit."
        }
        self.headers = {'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/80.0.3987.163 Safari/537.36'}

    # Events
    @commands.Cog.listener()
    async def on_ready(self):
        print('Intel Ark cog online')

    @commands.command()
    async def ark(self, ctx, *searchTerm):
        """Search for Intel CPUs"""
        if " ".join(searchTerm) in self.specialQueries:
            await ctx.send(embed=discord.Embed(colour=self.intelBlue,description=self.specialQueries[" ".join(searchTerm)]))
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

        url = f"https://ark.intel.com/content/www/us/en/ark/search.html?_charset_=UTF-8&q={cleanSearchTerm}"
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=self.headers, allow_redirects=True) as data:
                dataText = await data.text()
                page_soup = soup(dataText, "html.parser")
                await session.close()

        if (page_soup.find("input",{"id":"FormRedirectUrl"})): # if only one result
            url = page_soup.find("input",{"id":"FormRedirectUrl"}).get('value')
            url = f"https://ark.intel.com{url}"
            index = {}
            index['min'] = 1
            index['current'] = 1
            index['max'] = 1
            data = await self.get_cpu_data(url)
            embed = await self.make_ark_embed(data,index)
            await ctx.send(embed=embed)
            return

        if (page_soup.find("h2",text="No products matching your request were found.")): # if no products found
            embed = discord.Embed(colour=self.intelBlue,description=f"No results found for `{searchTerm}`")
            await ctx.send(embed=embed)
            return

        # build list of URLs
        results = page_soup.findAll("div",{"class":"search-result"})
        urls = []
        for item in results:
            if 'generation' in item.find("h4",{"class":"result-title"}).find("a").contents[0].strip().lower():
                continue
            else:
                url = item.find("h4",{"class":"result-title"}).find("a").get('href')
                url = f"https://ark.intel.com{url}"
                urls.append(url)

        index = {}
        index['min'] = 1
        if regexMatched == True:
            if int(matchedString.split('r=')[1]) <= 0:
                index['current'] = int(matchedString.split('r=')[1]) * -1
            else:
                index['current'] = int(matchedString.split('r=')[1])
        else:
            index['current'] = 1
        index['max'] = len(results)
        if index['current'] > index['max']:
            index['current'] = index['max']

        # make embed
        data = await self.get_cpu_data(urls[index['current']-1])
        embed = await self.make_ark_embed(data,index)

        if index['min'] == index['max']: # if there is only one result
            await ctx.send(embed=embed)
            return

        messageObject = await ctx.send(embed=embed)
        if (index['current'] == index['min']) and (index['current'] != index['max']): # if this is the first result, and there are multiple
            allowedEmojis = ['▶']
            for emoji in allowedEmojis:
                await messageObject.add_reaction(emoji)
        if (index['current'] != index['min']) and (index['current'] != index['max']): # if this is a middle result
            allowedEmojis = ['◀','▶']
            for emoji in allowedEmojis:
                await messageObject.add_reaction(emoji)
        if (index['current'] == index['max']) and (index['current'] != index['min']): # if this is the last result
            allowedEmojis = ['◀']
            for emoji in allowedEmojis:
                await messageObject.add_reaction(emoji)

        async def editResult(urls, index, messageObject):
            data = await self.get_cpu_data(urls[index['current']-1])
            embed = await self.make_ark_embed(data,index)
            await messageObject.edit(embed=embed)
            if (index['current'] == index['min']) and (index['current'] != index['max']): # if this is the first result, and there are multiple
                allowedEmojis = ['▶']
                for emoji in allowedEmojis:
                    await messageObject.add_reaction(emoji)
            if (index['current'] != index['min']) and (index['current'] != index['max']): # if this is a middle result
                allowedEmojis = ['◀','▶']
                for emoji in allowedEmojis:
                    await messageObject.add_reaction(emoji)
            if (index['current'] == index['max']) and (index['current'] != index['min']): # if this is the last result
                allowedEmojis = ['◀']
                for emoji in allowedEmojis:
                    await messageObject.add_reaction(emoji)

            def reaction_info_check(reaction,user):
                return user == ctx.author and reaction.message.id == messageObject.id

            try:
                reaction, user = await self.client.wait_for('reaction_add', timeout=120.0, check=reaction_info_check)
            except asyncio.TimeoutError:
                await messageObject.clear_reactions()
                return
            else:
                # Okay, the user has reacted with an emoji, let's find out which one!
                if reaction.emoji in allowedEmojis:
                    if reaction.emoji == '▶':
                        index['current'] = index['current'] + 1
                        await messageObject.clear_reactions()
                        await editResult(urls,index,messageObject)
                    if reaction.emoji == '◀':
                        index['current'] = index['current'] - 1
                        await messageObject.clear_reactions()
                        await editResult(urls,index,messageObject)

        def reaction_info_check(reaction,user):
            return user == ctx.author and reaction.message.id == messageObject.id

        try:
            reaction, user = await self.client.wait_for('reaction_add', timeout=120.0, check=reaction_info_check)
        except asyncio.TimeoutError:
            await messageObject.clear_reactions()
            return
        else:
            # Okay, the user has reacted with an emoji, let's find out which one!
            if reaction.emoji in allowedEmojis:
                if reaction.emoji == '▶':
                    index['current'] = index['current'] + 1
                    await messageObject.clear_reactions()
                    await editResult(urls,index,messageObject)
                if reaction.emoji == '◀':
                    index['current'] = index['current'] - 1
                    await messageObject.clear_reactions()
                    await editResult(urls,index,messageObject)

    async def get_cpu_data(self, url):
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=self.headers) as data:
                dataText = await data.text()
                page_soup = soup(dataText, "html.parser")
                await session.close()
        specs = {}
        specs['Url'] = url
        specs['ProcessorNumber'] = page_soup.find("span",{"class":"value","data-key":"ProcessorNumber"}).contents[0].strip()
        specs['CoreCount'] = page_soup.find("span",{"class":"value","data-key":"CoreCount"}).contents[0].strip()
        specs['ThreadCount'] = page_soup.find("span",{"class":"value","data-key":"ThreadCount"}).contents[0].strip()
        specs['HyperThreading'] = page_soup.find("span",{"class":"value","data-key":"HyperThreading"}).contents[0].strip()
        specs['ClockSpeed'] = page_soup.find("span",{"class":"value","data-key":"ClockSpeed"}).contents[0].strip()
        specs['SocketsSupported'] = page_soup.find("span",{"class":"value","data-key":"SocketsSupported"}).contents[0].strip()
        specs['MaxTDP'] = page_soup.find("span",{"class":"value","data-key":"MaxTDP"}).contents[0].strip()
        specs['AESTech'] = page_soup.find("span",{"class":"value","data-key":"AESTech"}).contents[0].strip()
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
        if data['ClockSpeedMax'] != None:
            embed.add_field(name='Clock Speed',value=f"{data['ClockSpeed']} / {data['ClockSpeedMax']}",inline=True)
        else:
            embed.add_field(name='Clock Speed',value=data['ClockSpeed'],inline=True)
        if data['HyperThreading'] == 'No':
            embed.add_field(name='Cores',value=data['CoreCount'],inline=True)
        elif data['HyperThreading'] == 'Yes':
            embed.add_field(name='Cores/Threads',value=f"{data['CoreCount']} / {data['ThreadCount']}",inline=True)
        embed.add_field(name='TDP',value=data['MaxTDP'],inline=True)
        if data['VTD'] != None:
            embed.add_field(name='VTD',value=data['VTD'],inline=True)
        embed.add_field(name='AES Tech',value=data['AESTech'],inline=True)
        embed.add_field(name='Sockets',value=data['SocketsSupported'],inline=True)
        embed.set_footer(text=f"{index['current']} of {index['max']}")
        return embed

def setup(client):
    client.add_cog(IntelArk(client))