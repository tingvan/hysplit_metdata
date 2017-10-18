# vim: tabstop=8 expandtab shiftwidth=4 softtabstop=4
from ecmwfapi import ECMWFDataServer
from calendar import monthrange
from calendar import month_name
from optparse import OptionParser
import sys
import datetime
import string

"""
MAIN PROGRAM: retrieves ecmwf ERA5 dataset.
PRGRMMR: Alice Crawford    ORG: CICS-MD  DATE:2017-10-16

PYTHON 2.7

ABSTRACT: Retrieves ECMWF ERA5 grib files for use by HYSPLIT.

Must have ecmwfapi installed. 
https://software.ecmwf.int/wiki/display/WEBAPI/Accessing+ECMWF+data+servers+in+batch
The api key must be stored in the $HOME/.ecmwfapirc file.
The api key can be found at https://api.ecmwf.int/v1/key/
For instructions on creating an ecmwf account and retrieving a key see
https://software/ecmwf.int/wiki/display/WEBAPI/ACESS_ECMWF+Public+Datasets

grib files can be input into the era52arl fortran utility program to create a meteorological file that can be used
as input into HYSPLIT. 

This python program aids in retrieving  meteorological variables from the ERA5 dataset which HYSPLIT needs.

for command line options run with --help

writes a file called get_era5_message.txt 
writes a file called new_api2arl.cfg


"""


def write_cfg(tparamlist, dparamlist, cfgname = 'new_api2arl.cfg'):
    """writes a .cfg file which is used by the fortran conversion program era52arl to
       read the grib files and convert them into a meteorological file that HYSPLTI can use.
    """
    #Key is HYSPLIT name
    #value is list of [ERA5 short name, ERA5 indicatorOfParamter, unit conversion]
    #unit conversion converts from units of the ERA5 to units that HYSPLIT expects.
    #the short name and indicatorOfParameter can be found by doing a grib_dump
    #or tables in the ERA5 documentation - 
    #https://software.ecmwf.int/wiki/display/CKB/ERA5+data+documentation#ERA5datadocumentaion-Paramterlistings
    print dparamlist
    sname = {}
    sname['TPP1'] = ['tp','228','1.0']       #units of m. multiplier is 1.          
    sname['SHTF'] = ['sshf','146','0.00028'] #units J/m^2 (surface sensible heat flux) (divide by 3600 to get W/m^2)     
    sname['DSWF'] = ['ssrd','169','0.00028'] #same as sshf           
    sname['LTHF'] = ['slhf','147','0.00028'] #same as sshf            
    sname['USTR'] = ['zust','3', '1.0']      #units of m/s (multiplier should be 1)      

    sname['TEMP'] = ['t', '130', '1.0']    #units K
    sname['UWND'] = ["u", '131', '1.0']    #units m/s
    sname['VWND'] = ["v", '132', '1.0']    #units m/s
    sname['WWND'] = ["w", '135', '0.01']   #units Pa/s. convert to hPa/s for HYSPLIT
    sname['RELH'] = ["r", '157', '1.0']    #units %
    sname['HGTS'] = ["z", '129', '0.102']  #units m^2 / s^2. Divide by 9.8m/s^2 to get meters.
    #sname['SPHU']= "q"     #units kg / kg category 1, number 0. multiplier is 1   #specific humidity. redundant since have RELH

    sname['T02M'] = ['2t', '167', '1.0']  #units K         #Analysis (needed) ERA5
    sname['U10M'] = ['10u','165', '1.0']  #units m/s       #Analysis (needed) ERA5
    sname['V10M'] = ['10v','166', '1.0']  #units m/s       #Analysis (needed) ERA5
    sname['PRSS'] = ['sp' ,'134', '0.01'] #Units Pa        #multiplier of 0.01 for hPa.
    sname['TCLD'] = ['tcc','164', '1.0']  #total cloud cover 0-1  
    sname['DP2M'] = ['2d', '168' , '1.0']   #2m dew point temperature  : Units K : level_indicator 1 , gds_grid_type 0

    sname['SHGT'] = ["z" , '129', '0.102']#units m^2 / s^2  
    sname['CAPE'] = ["cape", '59','1.0']  #units J/kg #multiplier of 1.
    sname['PBLH'] = ["blh", '159', '1.0'] #units m        


    numatm = str(len(tparamlist))
    atmgrb = ''
    atmcat = ''
    atmcnv = ''
    atmarl = ''
    for atm in tparamlist:
        atmgrb += "'" + sname[atm][0] + "', " 
        atmcat +=  sname[atm][1] + ", " 
        atmcnv +=  sname[atm][2] + ", " 
        atmarl += "'" + atm + "', "

    numsfc = str(len(dparamlist))
    sfcgrb = ''
    sfccat = ''
    sfccnv = ''
    sfcarl = ''
    for sfc in dparamlist:
        sfcgrb += "'" + sname[sfc][0] + "', " 
        sfccat +=  sname[sfc][1] + ", " 
        sfccnv +=  sname[sfc][2] + ", " 
        sfcarl += "'" + sfc + "', " 

    with open(cfgname, "w") as fid:
         #the -2 removes the last space and comma from the string.
         fid.write('&SETUP\n') 
         fid.write('numatm = ' + numatm +  ',\n') 
         fid.write('atmgrb = ' + atmgrb[:-2] + '\n')
         fid.write('atmcat = '  + atmcat[:-2] + '\n')
         fid.write('atmnum = ' + atmcat[:-2] + '\n')
         fid.write('atmcnv = ' + atmcnv[:-2] + '\n')
         fid.write('atmarl = ' + atmarl[:-2] + '\n')

         fid.write('numsfc = ' + numsfc +  ',\n') 
         fid.write('sfcgrb = ' + sfcgrb[:-2] + '\n')
         fid.write('sfccat = ' + sfccat[:-2] + '\n')
         fid.write('sfcnum = ' + sfccat[:-2] + '\n')
         fid.write('sfccnv = ' + sfccnv[:-2] + '\n')
         fid.write('sfcarl = ' + sfcarl[:-2] + '\n')
         fid.write('/\n')


def createparamstr(paramlist):
    """contains a dictionary of codes for the parameters to be retrieved. Input a list of string descriptors of the
       parameters. Output is a string of codes which can be used in the server.retrieve() function.
       4 letter codes used for dictionary keys correspond to codes used by fortran ecmwf2arl converter. 
       The sname dictionary has the same keys as the param dictionary but the values are the grib short_name."""
    param = {}
    sname = {}
    #Needed for 3D
    param['TEMP'] = "130.128"
    param['UWND'] = "131.128"
    param['VWND'] = "132.128"
    param['WWND'] = "135.128" 
    param['RELH'] = "157.128"              #No relative humidity  on model levels in ERA5. It is available on pressure levels.
    param['HGTS'] = "129.128"              #geopotential heights: this is also a 2D field.
                                           #for the model levels this is only archived on level 1.  
    #Optional for 3D
    param['SPHU']= '133.128'               #specific humidity. redundant since have RELH

    #2D analysis fields
    param['T02M'] = '167.128'              #Analysis (needed) ERA5
    param['U10M'] = '165.128'              #Analysis (needed) ERA5
    param['V10M'] = '166.128'              #Analysis (needed) ERA5
    param['DP2M'] = "168.128"              #(optional) Analysis: ERA5  2m dew point temperature  : Units K : level_indicator 1 , gds_grid_type 0
    param['PRSS'] = "134.128"              #(optional) Analysis: ERA5  pressure at surface. This is only archived once a day at 00Z.
    param['SHGT'] = "129.128"              #geopotential heights (????) ERA5 - these are in the 2d and model levels as well.
    param['TCLD'] = "164.128"              #(optional) Analysis: ERA5 total cloud cover
    param['CAPE'] = "59.128"               #(optional) Analysis: ERA5 convective available potential energy
    param['PBLH'] = "159.128"              #(optional) Analysis: ERA5 boundarly layer height
    param['XXXX'] = "244.128"              #(optional) Analysis: ERA5 forecast surface roughness shortname=fsr


    #2D forecast fields. These are all optional.
    ###"The accumulations in the short forecasts (from 06 and 18 UTC) of ERA5 are treated differently compared with those in ERA-INTERIM (where they
    ###were from the beginning of the forecast to the forecast step). In the short forecasts of ERA5, the accumulations are since the previous post processing (archiving)
    ### so for: HRES - accumulations are in the hour ending at the forecast step.
    ### mean rate parameters in ERA5 are similar to accumulations except that the quantities are averaged instead of accumulated over the period so the units
    ### includ "per second"
    ### step for forecast are 1 through 18
    
    param['TPP1'] = '228.128'              #Forecast: ERA5  short name tp, number 228, units (m)
    sname['TPP1'] = 'tp'             
    param['SHTF'] = '146.128'              #Forecast: ERA5 surface sensible heat flux. sshf, 146, Jm^(-2)
    sname['SHTF'] = 'sshf'              
    param['DSWF'] = "169.128"              #Forecast: ERA5 surface solar radiation downward, ssrd  Jm^(-2)
    sname['DSWF'] = "ssrd"             
    param['LTHF'] = "147.128"              #Forecast: ERA5 surface latent heat flux, slhf, 147, Jm^(-2)
    sname['LTHF'] = "slhf"             
    param['USTR'] = "3.228"                #Forecast: ERA5 friction velocity, short name = zust,  (m/s)
    sname['USTR'] = "zust"               
#----------------------------------------------------------------------------------------------------------------------------
    paramstr = ''
    i=0
    for key in paramlist:
        if key in param.keys():
            if i == 0:
               paramstr += param[key] 
            else:
               paramstr += '/' + param[key] 
            i+=1
        else:
            print "No code for " , key , " available." 
    return paramstr


def grib2arlscript(scriptname, file3d, file2d, filetppt, day, tstr, hname='ERA5'):
   """writes a line in a shell script to run era51arl. $MDL is the location of the era52arl program.
   """
   print "writing to " , scriptname
   fid = open(scriptname , 'a')

   inputstr = []
   inputstr.append('${MDL}/era52arl')
   inputstr.append('-i' + file3d)
   inputstr.append('-a' + file2d)         #analysis file with 2d fields
   if filetppt != '':
      inputstr.append('-f' + filetppt) #file with forecast fields.
   for arg in inputstr:
       fid.write(arg + ' ')
   fid.write('\n')
   tempname = tstr + '.ARL'
   fname = hname + day.strftime("_%Y%m%d.ARL")
   fid.write('mv DATA.ARL ' +  tempname + '\n')
   fid.write('mv MESSAGE MESSAGE.'  +fname + '.' + tstr + ' \n')
   if tstr=='T1':
      fid.write('cat ' + tempname + ' > ' +fname + '\n')
   else:
      fid.write('cat ' + tempname + ' >> ' +fname + '\n')
   fid.write('rm ' + tempname + '\n')
   fid.write('\n')
 
   fid.close()

##Parse command line arguments and set defaults#####
parser = OptionParser()
parser.add_option("-y", type="int" , dest="year", default=2000,
                  help="{2000} Year to retrieve. type integer.")
parser.add_option("-m", type="int" , dest="month" , default=1,
                  help = "{1} Month to retrieve. type integer")
parser.add_option("-d", type="int" , dest="day" , default='1',
                  help = "Default is to retrieve one day split into four files. ")
parser.add_option("-f", action="store_true" , dest="getfullday" , default=False, 
                  help = "If set then will retrieve one grib file per day. \
                          default is to split the 3d and 2d analysis files into 6 hour increments.\
                          The reason for this is that full day grib files for the global dataset will \
                          be too large for the conversion program. If a smaller area is being extracted then\
                          you may wish to use this option. The conversion program requires grib files less than\
                          2 gb in size. \
                          2d forecast is always retreived for the full day." )
parser.add_option("--dir", type="string" , dest="dir" , default='./',
                  help = "{./} Directory where files are to be stored. ")
parser.add_option("-o", type="string" , dest="fname" , default='',
                  help = "Output filename stem. 3D.grib and 2D.grib will be added on. \
                  The default is to call it DATASET_YYYY.MMM where MMM is the three letter abbreviation for month. \
                  If a day range is specified then the default will be DATASET_YYYY.MMM.dd-dd.")
parser.add_option("--3d", action="store_false" , dest="retrieve2d" , default='true',
                  help = "If set then it will only retrieve 3d data.")
parser.add_option("--noprecip", action="store_false" , dest="get_precip" , default= True, 
                  help = "Default is to retrieve 2D fields in a .2d.grib file which has analysis values for \
                          and a separate 2D file in a .2df.grib file which has forecast values. \
                          If the --noprecip field is set then the .2df.grib file will not be retrieved. \
                          ")
parser.add_option("--2d", action="store_false" , dest="retrieve3d" , default='true', 
                  help = "If set then it will only retrieve 2d data. The default is to retrieve both." \
                  "If --2d and --3d are both set then no data will be retrieved.")
parser.add_option("--check", action="store_false" , dest="run" , default='true', 
                  help = "If set then simply echo command. Do not retrieve data" )
parser.add_option("-g", action="store_true" , dest="grib2arl" , default= False, 
                  help = "If set then will append lines to a shell script for converting the files to arl format.") 
parser.add_option("-l", type="int" , dest="toplevel" , default= 1, 
                  help = "Set top pressure level to be retrieved. Default is to retrieve all levels. ")
#currently will only retrieve pressure levels. no converter available for model levels yet.
#parser.add_option("-t", type="string" , dest="leveltype" , default= "pl", 
#                  help = "default is pressure levels (pl) which will retrieve grib1 file \
#                          Can also choose model levels (ml). There are 137 model levels. This will retrieve grib2 file.") 
parser.add_option("--area", type="string" , dest="area" , default= "90/-180/-90/180", 
                  help = "choose the area to extract. Format is North/West/South/East \
                          North/West gives the upper left corner of the bounding box. \
                          South/East gives the lower right corner of the bounding box. \
                          Southern latitudes and western longiutdes are given negative numbers.") 




(options, args) = parser.parse_args()

get_precip = options.get_precip

#mid = open('recmwf.txt','w')
mfilename = 'get_era5_message.txt'

year = options.year
month = options.month
day = options.day
#monthstr = '%0*d' % (2, month)
#daystr = '%0*d' % (2, day)
dataset = 'era5'
area = options.area

startdate = datetime.datetime(year, month, day, 0)
tpptstart = startdate - datetime.timedelta(hours=24)  #need to retrieve forecast variables from previous day.

datestr = startdate.strftime('%Y-%m-%d') 
tppt_datestr = tpptstart.strftime('%Y-%m-%d') 

###"137 hybrid sigma/pressure (model) levels in the vertical with the top level at 0.01hPa. Atmospheric data are
###available on these levels and they are also interpolated to 37 pressure, 16 potential temperature and 1 potential vorticity level(s).

##model level fields are in grib2. All other fields (including pressure levels) are in grib1 format.
if options.leveltype == "pl":
    levtype = "pl"
elif options.leveltype == "ml":
    levtype = "ml"
else:
    print "WARNING: leveltype not supported. Only pl (pressure levels) or ml (model levels) supported"
    sys.exit()

##Pick pressure levels to retrieve. ################################################################
##Can only pick a top level 
if levtype == "pl":
    totlevs = {}
    totlevs['interim'] = 37
    totlevs['era5'] = 37
    nlevels = totlevs[dataset]
    #levs = range(750,1025,25) + range(150,750,50) + range(100,150,25) + [1,2,3,5,6,10,20,30,50,70]
    levs = range(750,1025,25) + range(300,750,50) + range(100,275,25) + [1,2,3,5,7,10,20,30,50,70]
    levs = sorted(levs)
    if options.toplevel == 1: 
       levstr = 'all'
    else:
       levs = filter(lambda y: y>=options.toplevel, levs)
       levstr = str(levs[0])
       nlevels = len(levstr)
       for lv in levs[1:]:
           levstr += '/' + str(lv)  
    print 'Retrieve levels ' , levstr
else:
    ##level 40 is about 24.5 km. Level 137 is 10 m
    ##level 49 is about 20 km.
    levstr = "/".join(map(str, range(49,137)))
##########################################################################################



options.dir = options.dir.replace('\"', '')
if options.dir[-1] != '/':
   options.dir += '/'

if options.fname =='':
   dstr = startdate.strftime('%Y.%b%d')
   dstr2 = startdate.strftime('%Y%b')
   f3d = dataset.upper() + '_' + dstr +  '.3d'
   f2d = dataset.upper() + '_' + dstr +  '.2d'
   ftppt = dataset.upper() + '_' + dstr +   '.2df'
else:    
   f3d = options.dir + options.fname  + '.3d'
   f2d = options.dir + options.fname  + '.2d'
   ftppt = options.dir + options.fname  + '.2df'
   
if levtype == 'ml':
   f3d += '.ml'
 
file3d = options.dir + f3d
file2d = options.dir + f2d
filetppt = options.dir + ftppt

#datestr = str(year) + monthstr + firstdaystr + '/to/' + str(year) + monthstr + lastdaystr
print "Retrieve for: " , datestr

server = ECMWFDataServer(verbose=False)


##wtype = "4v"   ##4D variational analysis is available as well as analysis.

wtype="an" 
##need to break each day into four time periods to keep 3d grib files at around 1.6 GB
wtime1 =  "00:00:00/01:00:00/02:00:00/03:00:00/04:00:00/05:00:00"
wtime2 =  "06:00:00/07:00:00/08:00:00/09:00:00/10:00:00/11:00:00"
wtime3 =  "12:00:00/13:00:00/14:00:00/15:00:00/16:00:00/17:00:00"
wtime4 =  "18:00:00/19:00:00/20:00:00/21:00:00/22:00:00/23:00:00"
if options.getfullday:
    wtimelist = [wtime1 + '/' + wtime2 + '/' + wtime3 + '/' + wtime4]
else: #retrieve day in 4 different files with 6 hour increments.
    wtimelist = [wtime1, wtime2, wtime3, wtime4]
#wtimelist = [wtime1]

###In order to make the forecast field files have matching time periods
###use the following times and steps.
###start at 18  on the previous day with step of 6 through 12 to get hours 0 through 05.
###hour 06 with step of 0 to 5 to get hours 6 through 11
###hour 06 with step of 6 to 11 to get hours 12 through 17
###hour 18 with step 0 through 5 to get hours 18 through 23

###NOTE - accumulated fields are 0 for step of 0. So cannot use step0.
##Always retrieve full day for the forecast fields.
#if options.getfullday:
ptimelist = ["18:00:00/06:00:00"]
pstep = ["/".join(map(str,range(1,13)))]
pstart=[tppt_datestr+ '/' + datestr]
#else:
#    ptime1 = "18:00:00"
#    step1 = "/".join(map(str, range(6,12)))
#    ptime2 = "06:00:00"
#    step2 = "/".join(map(str, range(0,6)))
#    ptime3 = "06:00:00"
#    step3 = "/".join(map(str, range(6,12)))
#    ptime4 = "18:00:00"
#    step4 = "/".join(map(str, range(0,6)))
#    pstart = [tppt_datestr, datestr, datestr, datestr]
#    ptime = [ptime1, ptime2, ptime3, ptime4]
#    pstep = [step1, step2, step3, step4]


#grid: 0.3/0.3: "For era5 data, the point interval on the native Gaussian grid is about 0.3 degrees. 
#You should set the horizontal resolution no higher than 0.3x0.3 degrees (about 30 km), approximating the irregular grid spacing
#on the native Gaussian grid.

iii=1
###SPLIT retrieval into four time periods so files will be smaller.
for wtime in wtimelist:
    print wtime
    if options.getfullday:
        tstr = '.D' + str(iii) + '.grib'
    else:
        tstr = '.T' + str(iii) + '.grib'
    ###need to set the grid parameter otherwise will not be on regular grid and converter will not handle.
    ####retrieving 3d fields
    if options.retrieve3d:
        ##have choice between getting pressure levels or model levels.
        #param3d = ['TEMP' , 'UWND', 'VWND' , 'WWND' , 'RELH' , 'HGTS', 'SPHU' ]
        if levtype=='pl':
            param3d = ['TEMP' , 'UWND', 'VWND' , 'WWND' , 'RELH' , 'HGTS' ]
        elif levtype=='ml':
            param3d = ['TEMP' , 'UWND', 'VWND' , 'WWND' , 'SPHU']
        paramstr = createparamstr(param3d)
        with open(mfilename, 'w') as mid: 
            mid.write('retrieving 3d data \n')
            mid.write(paramstr + '\n')
            mid.write('time ' + wtime + '\n')
            mid.write('type ' + wtype + '\n')
            mid.write('date ' + datestr + '\n')
            mid.write('-------------------\n')
        if options.run:
            server.retrieve({
                        'class'   : "ea",
                        'expver'  : "1",
                        'dataset' : dataset,
                        'stream'  : "oper",   #stays same for era5.
                        'levtype' :  levtype,
                        'levelist':  levstr,
                        'date'    :  datestr,
                        'time'    :  wtime,
                        'origin'  : "all",
                        'type'    :  wtype,
                        'param'   :  paramstr,
                        'target'  :  file3d  + tstr,
                        'grid'    : "0.3/0.3",
                        'area'    : area
                       })

    param2df = []
    param2da = []
    ####retrieving 2d fields
    if options.retrieve2d:
        param2da = ['T02M' , 'V10M' , 'U10M', 'TCLD', 'PRSS',  'DP2M', 'PBLH', 'CAPE', 'SHGT']
        paramstr = createparamstr(param2da)
        with open(mfilename, 'a') as mid: 
            mid.write('retrieving 2d data \n')
            mid.write(paramstr + '\n')
            mid.write('time ' + wtime + '\n')
            mid.write('type ' + wtype + '\n')
            mid.write('date ' + datestr + '\n')
            mid.write('-------------------\n')
        if options.run:
            server.retrieve({
                        'class'   : "ea",
                        'expver'  : "1",
                        'number'  : "0/1/2/3/4/5/6/7/8/9",
                        'dataset' : dataset,
                        #'step'    : stepsz,
                        'stream'  : "oper",
                        'levtype' : "sfc",
                        'date'    :  datestr,
                        'time'    :  wtime,
                        #'origin'  : "all",
                        'type'    :  wtype,
                        'param'   :  paramstr,
                        'target'  : file2d + tstr,
                        'grid'    : "0.3/0.3",
                        'area'    : area
                           })

    if options.grib2arl:
       sname = options.dir + dstr2 + '_ecm2arl.sh'
       grib2arlscript(sname, f3d+tstr, f2d+tstr, ftppt+tstr, startdate, 'T'+str(iii)) 
    iii+=1

iii=1 
for ptime in ptimelist:
    if options.retrieve2d and get_precip:
           ### "The short forecasts fun from 06 and 18 UTC, have hourly steps from 0 to 18 hours
           ### here we cover the 24 hour time period by starting the retrieval from the day before.
           ### This is not going to match the time periods for the analysis variables.
           ### conversion program will handle extra time periods in the forecast file.
           #precipstep = "/".join(map(str, range(0,12)))
           #preciptime = "06:00:00/18:00:00"
           #These surface fields are only available as forecast. 
           with open(mfilename, 'a') as mid: 
               mid.write('retrieving 2d forecast data \n')
               mid.write(paramstr + '\n')
               mid.write('time ' + ptime + '\n')
               mid.write('step ' + pstep[iii-1] + '\n')
               mid.write('type ' + 'fc' + '\n')
               mid.write('date ' + tppt_datestr + '\n')
           param2df = ['TPP1', 'SHTF' , 'DSWF', 'LTHF', 'USTR']
           paramstr = createparamstr(param2df)
           if options.run:
            server.retrieve({
                               'class'   : "ea",
                               'expver'  : "1",
                               'dataset' : dataset,
                                'stream'  : "oper",
                                'levtype' : "sfc",
                                'date'    : pstart[iii-1],
                                'time'    : ptime,
                                'step'    : pstep[iii-1],
                                #'origin'  : "all",
                                'type'    : "fc",
                                'param'   :  paramstr,
                                'target'  : filetppt + tstr,
                                'grid'    : "0.3/0.3",
                                'area'    : area
                        })
    iii+=1

param2da.extend(param2df)
#write a cfg file for the converter.
write_cfg(param3d, param2da)
mid.close()

#Notes on the server.retrieve function.
#Seperate lists with a /
#indicate a range by value/to/value/by/step
#type : an = analysis , fc = forecast
#levtype: pl, ml, sfc, pt, pv  (pressure level, model level, mean sea level, potential temperature, potential vorticity)

#An area and grid keyword are available but not used here.
#Area : four values : North West South East
#Grid : two values  : West-East   North-South increments
#could use 'format' : 'netcdf' if want netcdf files.

