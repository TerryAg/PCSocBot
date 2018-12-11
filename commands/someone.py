from commands.base import Command
from helpers import *

from collections import defaultdict
import random
import json
import re

IDENTIFIER = "{}"
FORMAT_FILE = "files/formats.json"
PEOPLE_LIMIT = 100  # to minimise API spam
CHAR_LIMIT = 2000


class Someone(Command):
    desc = "This command is used to roll for a random member of the server"

    def eval(self, people=1):
        # Create our own member list
        member_list = list(self.members)

        # Initialise vars
        roll = 0
        roll_list = []

        try:
            people = int(people)
        except ValueError:
            raise CommandFailure(
                "Must supply either an integer or subcommand!")

        # Enforce limit on people requested by the command
        if people > PEOPLE_LIMIT:
            raise CommandFailure(f"The maximum number of supported {code('people')} is "
                                 f"{bold(PEOPLE_LIMIT)}. Sorry!")

        # Assert that people is greater than 0
        people = max(people, 1)

        # Assert that the people does not exceed the members
        people = min(people, len(member_list))

        for _ in range(people):
            # Get random member from member list
            roll = random.randrange(len(member_list))

            # Append to our roll list
            rolled = member_list[roll-1]
            roll_list.append(rolled)

            # Remove the member from the member list
            member_list.remove(rolled)

        # Retrieve a random format from the json
        try:
            # Get the format dict, throws FileNotFoundError
            with open(FORMAT_FILE, 'r') as fmt:
                formats = json.load(fmt)

            # Randomly choose from the people indexing, throws KeyError
            if len(formats[str(people)]) == 0:
                raise KeyError
            else:
                out = random.choice(formats[str(people)])

        except (FileNotFoundError, KeyError):
            # No format for that number of people, use default
            out = "{}" + " {}"*(people-1)

        roll_list = [bold(nick(x)) for x in roll_list]

        # Craft output string according to format
        return "\n".join(out.format(*roll_list).split("\\n"))


class Add(Someone):
    desc = """Adds a format template. Mods only. 
    `format_string`: String containing `people` number of {}, 
    where `{}` is replaced by a random **someone**
    """
    roles_required = ['mod', 'exec']

    def eval(self, *format_string):
        # Get the format string
        format_string = " ".join(format_string)

        # Count the number of people to generate
        people = count_placeholders(format_string)

        # Make sure the number of people is sane
        if people < 1:
            raise CommandFailure(
                "Invalid format string, must have at least 1 `{}`!")

        # Check that the string provided can be used with str.format
        try:
            format_string.format(*['a']*people)
        except ValueError:
            raise CommandFailure(
                "Invalid format string, please remove single curly braces")

        # Open the JSON file or create a new dict to load
        formats = defaultdict(list)
        try:
            with open(FORMAT_FILE, 'r') as old:
                formats.update(json.load(old))
        except FileNotFoundError:
            pass

        # Add the format string to the key
        formats[str(people)].append(format_string)

        # Write the formats to the JSON file
        with open(FORMAT_FILE, 'w') as new:
            json.dump(formats, new)

        return f"Your format {code(format_string)} for {bold(people)} people has been added!"


class Remove(Someone):
    desc = """Removes a format template. 
    Passing a number removes all formats for those people. Mods only."""

    roles_required = ['mod', 'exec']

    def eval(self, *format_string):

        # Get the format string
        format_string = " ".join(format_string)

        if not format_string:
            raise CommandFailure("Must supply a format string!")

        # If a number is passed into the second argument, set remove_all flag
        try:
            people = int(format_string)
            remove_all = True
        except ValueError:
            remove_all = False
            # Get people
            people = count_placeholders(format_string)

        try:
            # Open the JSON file or create a new dict to load
            with open(FORMAT_FILE, 'r') as fmt:
                formats = json.load(fmt)

            if remove_all:
                # Remove all format strings for people
                del formats[str(people)]
                out = f"Removed all formats for {bold(people)} people!"
            else:
                # Remove format string if in the dict
                formats[str(people)].remove(format_string)
                out = f"The format {code(format_string)} " \
                    f"for {bold(people)} people was removed!"

        except (FileNotFoundError, KeyError, ValueError):
            return f"Format {code(format_string)} not found!"

        # Write the formats to the JSON file
        with open(FORMAT_FILE, 'w') as new:
            json.dump(formats, new)

        return out


class List(Someone):
    desc = "Lists the formats for the given number of `people`."

    async def eval(self, people=None):

        try:
            # Open the JSON file
            with open(FORMAT_FILE, 'r') as fmt:
                formats = json.load(fmt)
        except FileNotFoundError:
            return "No formats."

        if people is not None:
            # User has specified number of people
            try:
                int(people)
            except ValueError:
                raise CommandFailure(f"`people` must be an integer value!")

            # List all the entries for people
            if not (people in formats and formats[people]):
                return f"No formats for {bold(people)} people."

            out = f"Formats for {bold(people)} `people`:\n"

            #out += "\n".join(formats[people])
            for entry in formats[people]:
                tmp = entry + "\n"
                if len(out+tmp) > CHAR_LIMIT:
                    # out exceeds character limit,
                    # send message and truncate out
                    await self.client.send_message(self.message.channel,
                                                   out)
                    out = tmp
                else:
                    out += tmp
        else:
            # List all entries
            out = "All formats:\n"
            empty = True

            # Sort by numeric value of keys
            for k, v in sorted(formats.items(), key=lambda x: int(x[0])):
                if v:
                    empty = False
                    tmp = f"Formats for {bold(k)} `people`:\n"

                    if len(out+tmp) > CHAR_LIMIT:
                        # out exceeds character limit,
                        # send message and truncate out
                        await self.client.send_message(self.message.channel,
                                                       out)
                        out = tmp
                    else:
                        out += tmp

                    #tmp += "\n".join(v) + "\n"
                    for entry in v:
                        tmp = entry + "\n"
                        if len(out+tmp) > CHAR_LIMIT:
                            # out exceeds character limit,
                            # send message and truncate out
                            await self.client.send_message(self.message.channel,
                                                           out)
                            out = tmp
                        else:
                            out += tmp

            if empty:
                out = "No formats."

        return out


class Ls(Someone):
    desc = f"See {bold(code('!someone'))} {bold(code('list'))}."

    async def eval(self, people=None):
        return await List.eval(self, people)


class NoFormatsError(Exception):
    pass


def count_placeholders(format_string):
    """
    Counts the number of identifiers in the string. If none, defaults to -1.
    """
    return format_string.count(IDENTIFIER) or 1 + \
        max([int(x)
             for x in re.findall(r"{(\d*)}", format_string)], default=-1)
