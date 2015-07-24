# alliance-converter
Extract and convert match data from public-crest endpoints.
This could enable determined probe users to create their own animated scenes, based on alliance tournament matches.

# How to use it
The script takes two parameters
1.  The base-url to the tournament match, such as **http://public-crest-sisi.testeveonline.com/tournaments/4/series/120/matches/0/**
2.  The path to your eve probe res folder, usually **C:\ProgramData\CCP\EVE\SharedCache\probe\res**

```
python main.py https://public-crest.eveonline.com/tournaments/4/series/120/matches/0/ C:\ProgramData\CCP\EVE\SharedCache\probe\res
```
This would create the following files under **C:\ProgramData\CCP\EVE\SharedCache\probe\res**:  
curves\THE R0NIN vs The Tuskers Co..red  
sequences\THE R0NIN vs The Tuskers Co..yaml  

The .yaml file is an EveProbe scene file, but the .red file contains the curves that each actor follows.

The script can also take an optional -f parameter in order to have the camera follow a particular actor. The number used to specify which actor to follow is the ObjectId, and it can be found by digging through either the CREST data or the generated scene file.
```
python main.py https://public-crest.eveonline.com/tournaments/4/series/120/matches/0/ C:\ProgramData\CCP\EVE\SharedCache\probe\res -f 1015849493628 
```

# Notes
 - Currently only parses ships, drones, turrets and shooting.
 - No planets or static objects at the current time.
 - Ship flight looks pretty choppy as ships fly in straight lines between points specified from the crest endpoints.
 - Until Galatea is released, this script can only be used on http://public-crest-sisi.testeveonline.com, so if you want to run the example, that would be http://public-crest-sisi.testeveonline.com/tournaments/4/series/120/matches/0/
 - Make sure to run Eve Probe version 0.90.7403.0 or later (The probe version, not the launcher version. Can be viewed in the bottom-right corner of the Eve Probe launcher or the settings menu).