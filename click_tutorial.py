'''
An overview of how to build command line interfaces in click via 
manipulating a document I transcribed via AssemblyAI
We'll cover the following click decorators:
@click.group()
@click.command()
@click.argument()
@click.option()
@click.pass_context
@click.pass_obj
@click.invoke()
We will also cover how to make your own pass decorator via click.make_pass_decorator

We'll do these through the following functions:
check_context_object
get_keys
get_key
get_results
get_summary
get_text

Author: Yujian Tang
'''
import requests
import click
import json
import pprint
import sys
from time import sleep
from configure import auth_key

'''
@click.group(<name>) creates a command that instantiates a group class
a group is intended to be a set of related commands
@click.argument(<argument name>) tells us that we will be passing an argument
and referring to that argument in the function by the name we pass it
@click.pass_context tells the group command that we're going to be using
the context, the context is not visible to the command unless we pass this

In our example we'll name our group "cli"
'''
@click.group("cli")
@click.pass_context
@click.argument("document")
def cli(ctx, document):
    """An example CLI for interfacing with a document"""
    _stream = open(document)
    _dict = json.load(_stream)
    _stream.close()
    ctx.obj = _dict

'''
@click.command(<name>) creates a command that can be called with
the name that we pass through

Here we'll create an example command that prints out our context object,
which we expect to be a json looking dictionary
'''
@cli.command("check_context_object")
@click.pass_context
def check_context(ctx):
    pprint.pprint(type(ctx.obj))

'''
Here we'll make a pass decorator, which we can use to pass
the last object stored of a type of our choosing in the context
by using click.make_pass_decorator(<type>)
'''
pass_dict = click.make_pass_decorator(dict)

'''
click.echo is click's version of the echo command
click.style lets us style our output
click.secho is a command that takes a message, and a style command,
is a combination of click.echo and click.style

This command returns the keys to our dictionary object and
demonstrates how to use click.echo, click.style, and click.secho
'''
@cli.command("get_keys")
@pass_dict
def get_keys(_dict):
    keys = list(_dict.keys())
    click.secho("The keys in our dictionary are", fg="green")
    click.echo(click.style(keys, fg="blue"))

@cli.command("get_key")
@click.argument("key")
@click.pass_context
def get_key(ctx, key):
    pprint.pprint(ctx.obj[key])

'''
@click.option(<one dash usage>, <two dash usage>, is_flag (optional), help = <help>)
is how we can pass options to our command

We'll create a function that gets the "results" of our dictionary
and we will pass it two optional arguments, one to specify that
we want a specific key from the results, and a flag to indicate
whether or not we want to save our results to a json file
'''
@cli.command("get_results")
@click.option("-d", "--download", is_flag=True, help="Pass to download the result to a json file")
@click.option("-k", "--key", help="Pass a key to specify that key from the results")
@click.pass_context
def get_results(ctx, download: bool, key: str):
    results = ctx.obj['results']
    if key is not None:
        result = {}
        for entry in results:
            if key in entry:
                if key in result:
                    result[key] += entry[key]
                else:
                    result[key] = entry[key]
        results = result
    if download:
        if key is not None:
            filename = key+'.json'
        else:
            filename = "results.json"
        with open(filename, 'w') as w:
            w.write(json.dumps(results))
        print("File saved to", filename)
    else:
        pprint.pprint(results)

'''
click.invoke(<command>, <args>) is click's way of letting us
arbitrarily nest commands. NOTE: this command can only be used
when both the command being invoked AND the the command
doing the invoking use @click.pass_context

Since we already have a get_key command, we can just call that 
to print out a summary
'''
@cli.command("get_summary")
@click.pass_context
def get_summary(ctx):
    ctx.invoke(get_key, key="summary")

'''
@click.pass_obj is similar to @click.pass_context, instead
of passing the whole context, it only passes context.obj

We'll do something fun with our text extractor, we'll include
options to extract as either paragraphs or sentences, and 
default to returning one big block of text
'''
@cli.command("get_text")
@click.option("-s", "--sentences", is_flag=True, help="Pass to return sentences")
@click.option("-p", "--paragraphs", is_flag=True, help="Pass to return paragraphs")
@click.option("-d", "--download", is_flag=True, help="Download as a json file")
@click.pass_obj
def get_text(_dict, sentences, paragraphs, download):
    """Returns the text as sentences, paragraphs, or one block by default"""
    results = _dict['results']
    text = {}
    for idx, entry in enumerate(results):
        if paragraphs:
            text[idx] = entry['text']
        else:
            if 'text' in text:
                text['text'] += entry['text']
            else:
                text['text'] = entry['text']
    if sentences:
        sentences = text['text'].split('.')
        for i in range(len(sentences)):
            if sentences[i] != '':
                text[i] = sentences[i]
        del text['text']
    pprint.pprint(text)
    if download:
        if paragraphs:
            filename = "paragraphs.json"
        elif sentences:
            filename = "sentences.json"
        else:
            filename = "text.json"
        with open(filename, 'w') as w:
            w.write(json.dumps(results))
        print("File saved to", filename)

'''
I'm going to create a second group of commands that will
let us get the paragraphs and sentences directly from AssemblyAI
We'll also take advantage of this interaction to demonstrate
how to have two different groups of commands coexist in the 
same file.
'''
transcript_endpoint = "https://api.assemblyai.com/v2/transcript"
upload_endpoint = 'https://api.assemblyai.com/v2/upload'
headers = {
    "authorization": auth_key,
    "content-type": "application/json"
}
CHUNK_SIZE = 5242880

@click.group("assembly")
@click.pass_context
@click.argument("location")
def assembly(ctx, location):
    """A CLI for interacting with AssemblyAI"""
    def read_file(location):
        with open(location, 'rb') as _file:
            while True:
                data = _file.read(CHUNK_SIZE)
                if not data:
                    break
                yield data
            
    upload_response = requests.post(
        upload_endpoint,
        headers=headers, data=read_file(location)
    )
    audio_url = upload_response.json()['upload_url']
    print('Uploaded to', audio_url)
    transcript_request = {
        'audio_url': audio_url,
        'iab_categories': 'True',
    }

    transcript_response = requests.post(transcript_endpoint, json=transcript_request, headers=headers)
    transcript_id = transcript_response.json()['id']
    polling_endpoint = transcript_endpoint + "/" + transcript_id
    print("Transcribing at", polling_endpoint)
    polling_response = requests.get(polling_endpoint, headers=headers)
    while polling_response.json()['status'] != 'completed':
        sleep(30)
        print("Transcript processing ...")
        try:
            polling_response = requests.get(polling_endpoint, headers=headers)
        except:
            print("Expected to wait 30 percent of the length of your video")
            print("After wait time is up, call poll with id", transcript_id)
            return transcript_id
    categories_filename = transcript_id + '_categories.json'
    with open(categories_filename, 'w') as f:
        f.write(json.dumps(polling_response.json()['iab_categories_result']))
    print('Categories saved to', categories_filename)
    ctx.obj = polling_response.json()['id']

@assembly.command("get_sentences")
@click.pass_context
def get_sentences(ctx):
    sentences_endpoint = transcript_endpoint + "/" + ctx.obj + "/sentences"
    sentences_response = requests.get(sentences_endpoint, headers=headers)
    pprint.pprint(sentences_response.json())

@assembly.command("get_paragraphs")
@click.pass_context
def get_paragraphs(ctx):
    paragraphs_endpoint = transcript_endpoint + "/" + ctx.obj + "/paragraphs"
    paragraphs_response = requests.get(paragraphs_endpoint, headers=headers)
    pprint.pprint(paragraphs_response.json())

def main():
    if ".json" in sys.argv[1]:
        cli(prog_name="cli")
    if ".mp3" in sys.argv[1]:
        assembly(prog_name="assembly")

if __name__ == '__main__':
    main()