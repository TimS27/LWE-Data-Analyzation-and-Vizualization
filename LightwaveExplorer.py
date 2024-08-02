import numpy as np
import re
import os
import io
from scipy.optimize import least_squares
import yaml
import urllib.request
import zipfile
import tempfile
class lightwaveExplorerResult:
    """
    A class which contains the result of a Lightwave Explorer simulation
    The parameters of the simulation run are read from the .txt file
    generated by the simulation, and the binaries of the results,
    the electric field vs. time and space, and the spectra, both
    polarization-resolved, are loaded if available.

    :param filePath: The path to the .txt file describing the simulation result
    :type filePath: str

    :param loadFieldArray: Set to False in order to not load the electric field
    :type loadFieldArray: bool
    """
    def __init__(self, filePath: str, loadFieldArray=True):

        #list of all parameter names in order as they will be found in the simulation file
        parameterNames = ["pulseEnergy1",
                          "pulseEnergy2",
                          "frequency1",
                          "frequency2",
                          "bandwidth1",
                          "bandwidth2",
                          "superGaussianOrder1",
                          "superGaussianOrder2",
                          "cePhase1",
                          "cePhase2",
                          "delay1",
                          "delay2",
                          "gdd1",
                          "gdd2",
                          "tod1",
                          "tod2",
                          "phaseMaterialIndex1",
                          "phaseMaterialIndex2",
                          "phaseMaterialThickness1",
                          "phaseMaterialthickness2",
                          "BeamModeParameter",
                          "beamwaist1",
                          "beamwaist2",
                          "x01",
                          "x02",
                          "y01",
                          "y02",
                          "z01",
                          "z02",
                          "propagationAngle1",
                          "propagationAngle2",
                          "propagationAnglePhi1",
                          "propagationAnglePhi2",
                          "polarizationAngle1",
                          "polarizationAngle2",
                          "circularity1",
                          "circularity2",
                          "materialIndex",
                          "materialIndexAlternate",
                          "crystalTheta",
                          "crystalPhi",
                          "spatialWidth",
                          "spatialHeight",
                          "spatialStep",
                          "timeSpan",
                          "timeStep",
                          "crystalThickness",
                          "propagationStep",
                          "nonlinearAbsorptionStrength",
                          "bandGapElectronVolts",
                          "effectiveMass",
                          "drudeGamma",
                          "symmetryType",
                          "batchIndex",
                          "batchDestination",
                          "Nsims",
                          "batchIndex2",
                          "batchDestination2",
                          "Nsims2"]
        if filePath.endswith(".zip"):
            isZip = True
            archive = zipfile.ZipFile(filePath, 'r')
            directory, archiveName = os.path.split(filePath)
            fileBase, baseExtension = os.path.splitext(archiveName)
            settingsFile = archive.open(fileBase+'.txt')
            settingsFile = io.TextIOWrapper(settingsFile,'utf-8')
            
        else:
            isZip = False
            settingsFile = open(filePath, "r")
            fileBase = os.path.splitext(filePath)
        lines = settingsFile.readlines()

        def readLine(line: str):
            rr = re.findall(r"[-+]?[.]?[\d]+(?:,\d\d\d)*[\.]?\d*(?:[eE][-+]?\d+)?", line)
            return float(rr[-1])

        for i in range(len(parameterNames)):
            setattr(self, parameterNames[i], readLine(lines[i]))

        #correct type of integer parameters
        self.Nsims = int(self.Nsims)
        self.Nsims2 = int(self.Nsims2)
        self.symmetryType = int(self.symmetryType)
        self.batchIndex = int(self.batchIndex)
        self.batchIndex2 = int(self.batchIndex2)

        #Additional derived parameters
        MIN_GRIDDIM=8
        self.Ntime = int(MIN_GRIDDIM * np.round(self.timeSpan / (MIN_GRIDDIM * self.timeStep)))
        self.Nfreq = int(self.Ntime/2 + 1)
        self.fStep = 1.0/(self.Ntime * self.timeStep)
        self.Nspace = int(MIN_GRIDDIM * np.round(self.spatialWidth / (MIN_GRIDDIM * self.spatialStep)))
        if self.symmetryType == 2 or self.symmetryType == 4:
            self.Nspace2 = int(MIN_GRIDDIM * np.round(self.spatialHeight / (MIN_GRIDDIM * self.spatialStep)))
        else:
            self.Nspace2 = 1
        self.Ngrid = int(self.Ntime*self.Nspace*self.Nspace2)

        #now load the output data from binary format. Note that this will fail if you're using wrong-endian CPUs
        if loadFieldArray: 
            if self.symmetryType == 2 or self.symmetryType == 4:
                if isZip:
                    file = archive.open(fileBase+'_Ext.dat')
                    Ext = np.reshape(np.frombuffer(file.read(),dtype=np.double)[0:(2*self.Ngrid*self.Nsims*self.Nsims2)],(self.Ntime,self.Nspace,self.Nspace2, 2*self.Nsims,self.Nsims2),order='F')
                else:
                    Ext = np.reshape(np.fromfile(fileBase[0]+"_Ext.dat",dtype=np.double)[0:(2*self.Ngrid*self.Nsims*self.Nsims2)],(self.Ntime,self.Nspace,self.Nspace2, 2*self.Nsims,self.Nsims2),order='F')
                self.Ext_x = np.squeeze(Ext[:,:,:,0:(2*self.Nsims):2,:])
                self.Ext_y = np.squeeze(Ext[:,:,:,1:(2*self.Nsims + 1):2,:])
            else:
                if isZip:
                    file = archive.open(fileBase+'_Ext.dat')
                    Ext = np.reshape(np.frombuffer(file.read(),dtype=np.double)[0:(2*self.Ngrid*self.Nsims*self.Nsims2)],(self.Ntime,self.Nspace, 2*self.Nsims, self.Nsims2),order='F')
                else:
                    Ext = np.reshape(np.fromfile(fileBase[0]+"_Ext.dat",dtype=np.double)[0:(2*self.Ngrid*self.Nsims*self.Nsims2)],(self.Ntime,self.Nspace, 2*self.Nsims, self.Nsims2),order='F')
                self.Ext_x = np.squeeze(Ext[:,:,0:(2*self.Nsims):2,:])
                self.Ext_y = np.squeeze(Ext[:,:,1:(2*self.Nsims + 1):2,:])
        if isZip:
            file = archive.open(fileBase+'_spectrum.dat')
            RawSpectrum = np.reshape(np.frombuffer(file.read(),dtype=np.double)[0:3*self.Nfreq*self.Nsims*self.Nsims2],(self.Nfreq,3,self.Nsims,self.Nsims2),order='F')
        else:
            RawSpectrum = np.reshape(np.fromfile(fileBase[0]+"_spectrum.dat",dtype=np.double)[0:3*self.Nfreq*self.Nsims*self.Nsims2],(self.Nfreq,3,self.Nsims,self.Nsims2),order='F')
        self.spectrumTotal = np.squeeze(RawSpectrum[:,2,:,:]).T
        self.spectrum_x = np.squeeze(RawSpectrum[:,0,:,:]).T
        self.spectrum_y = np.squeeze(RawSpectrum[:,1,:,:]).T
        
        #make scale vector corresponding to the batch scan and correct units of the scan
        #apologies for the ugly elif block
        #double apologies that it appears twice for the two batches
        if self.batchIndex == 0:
            self.batchStart = 0
        elif self.batchIndex == 1:
            self.batchStart = self.pulseEnergy1
        elif self.batchIndex == 2:
            self.batchStart = self.pulseEnergy2
        elif self.batchIndex == 3:
            self.batchStart = self.frequency1
            self.batchDestination *= 1e12
        elif self.batchIndex == 4:
            self.batchStart = self.frequency2
            self.batchDestination *= 1e12
        elif self.batchIndex == 5:
            self.batchStart = self.frequency1
            self.batchDestination *= 1e12
        elif self.batchIndex == 6:
            self.batchStart = self.frequency2
            self.batchDestination *= 1e12
        elif self.batchIndex == 7:
            self.batchStart = self.cePhase1
            self.batchDestination *= np.pi
        elif self.batchIndex == 8:
            self.batchStart = self.cePhase2
            self.batchDestination *= np.pi
        elif self.batchIndex == 9:
            self.batchStart = self.delay1
            self.batchDestination *= 1e-15
        elif self.batchIndex == 10:
            self.batchStart = self.delay2
            self.batchDestination *= 1e-15
        elif self.batchIndex == 11:
            self.batchStart = self.gdd1
            self.batchDestination *= 1e-30
        elif self.batchIndex == 12:
            self.batchStart = self.gdd2
            self.batchDestination *= 1e-30
        elif self.batchIndex == 13:
            self.batchStart = self.tod1
            self.batchDestination *= 1e-45
        elif self.batchIndex == 14:
            self.batchStart = self.tod2
            self.batchDestination *= 1e-45   
        elif self.batchIndex == 15:
            self.batchStart = self.phaseMaterialThickness1
            self.batchDestination *= 1e-6
        elif self.batchIndex == 16:
            self.batchStart = self.phaseMaterialThickness2
            self.batchDestination *= 1e-6
        elif self.batchIndex == 17:
            self.batchStart = self.beamwaist1
            self.batchDestination *= 1e-6
        elif self.batchIndex == 18:
            self.batchStart = self.beamwaist2
            self.batchDestination *= 1e-6
        elif self.batchIndex == 19:
            self.batchStart = self.x01
            self.batchDestination *= 1e-6
        elif self.batchIndex == 20:
            self.batchStart = self.x02
            self.batchDestination *= 1e-6
        elif self.batchIndex == 21:
            self.batchStart = self.z01
            self.batchDestination *= 1e-6
        elif self.batchIndex == 22:
            self.batchStart = self.z02
            self.batchDestination *= 1e-6
        elif self.batchIndex == 23:
            self.batchStart = self.propagationAngle1
            self.batchDestination *= (np.pi/180)
        elif self.batchIndex == 24:
            self.batchStart = self.propagationAngle2
            self.batchDestination *= (np.pi/180)
        elif self.batchIndex == 25:
            self.batchStart = self.polarizationAngle1
            self.batchDestination *=(np.pi/180)
        elif self.batchIndex == 26:
            self.batchStart = self.polarizationAngle2
            self.batchDestination *= (np.pi/180)
        elif self.batchIndex == 27:
            self.batchStart = self.circularity1
        elif self.batchIndex == 28:
            self.batchStart = self.circularity2
        elif self.batchIndex == 29:
            self.batchStart = self.crystalTheta
            self.batchDestination *= (np.pi/180)
        elif self.batchIndex == 30:
            self.batchStart = self.crystalPhi
            self.batchDestination *= (np.pi/180)
        elif self.batchIndex == 31:
            self.batchStart = self.nonlinearAbsorptionStrength
        elif self.batchIndex == 32:
            self.batchStart = self.drudeGamma
            self.batchDestination *= 1e12
        elif self.batchIndex == 33:
            self.batchStart = self.effectiveMass
        elif self.batchIndex == 34:
            self.batchStart = self.crystalThickness
            self.batchDestination *= 1e-6
        elif self.batchIndex == 35:
            self.batchStart = self.propagationStep
            self.batchDestination *= 1e-9
        elif self.batchIndex == 36:
            self.batchStart = 0
        elif self.batchIndex == 37:
            self.batchStart = 0
        self.batchVector = np.linspace(self.batchStart,self.batchDestination,self.Nsims)

        #make second scale vector corresponding to the batch scan and correct units of the scan
        if self.batchIndex2 == 0:
            self.batchStart2 = 0
        elif self.batchIndex2 == 1:
            self.batchStart2 = self.pulseEnergy1
        elif self.batchIndex2 == 2:
            self.batchStart2 = self.pulseEnergy2
        elif self.batchIndex2 == 3:
            self.batchStart2 = self.frequency1
            self.batchDestination2 *= 1e12
        elif self.batchIndex2 == 4:
            self.batchStart2 = self.frequency2
            self.batchDestination2 *= 1e12
        elif self.batchIndex2 == 5:
            self.batchStart2 = self.frequency1
            self.batchDestination2 *= 1e12
        elif self.batchIndex2 == 6:
            self.batchStart2 = self.frequency2
            self.batchDestination2 *= 1e12
        elif self.batchIndex2 == 7:
            self.batchStart2 = self.cePhase1
            self.batchDestination2 *= np.pi
        elif self.batchIndex2 == 8:
            self.batchStart2 = self.cePhase2
            self.batchDestination2 *= np.pi
        elif self.batchIndex2 == 9:
            self.batchStart2 = self.delay1
            self.batchDestination2 *= 1e-15
        elif self.batchIndex2 == 10:
            self.batchStart2 = self.delay2
            self.batchDestination2 *= 1e-15
        elif self.batchIndex2 == 11:
            self.batchStart2 = self.gdd1
            self.batchDestination2 *= 1e-30
        elif self.batchIndex2 == 12:
            self.batchStart2 = self.gdd2
            self.batchDestination2 *= 1e-30
        elif self.batchIndex2 == 13:
            self.batchStart2 = self.tod1
            self.batchDestination2 *= 1e-45
        elif self.batchIndex2 == 14:
            self.batchStart2 = self.tod2
            self.batchDestination2 *= 1e-45   
        elif self.batchIndex2 == 15:
            self.batchStart2 = self.phaseMaterialThickness1
            self.batchDestination2 *= 1e-6
        elif self.batchIndex2 == 16:
            self.batchStart2 = self.phaseMaterialThickness2
            self.batchDestination2 *= 1e-6
        elif self.batchIndex2 == 17:
            self.batchStart2 = self.beamwaist1
            self.batchDestination2 *= 1e-6
        elif self.batchIndex2 == 18:
            self.batchStart2 = self.beamwaist2
            self.batchDestination2 *= 1e-6
        elif self.batchIndex2 == 19:
            self.batchStart2 = self.x01
            self.batchDestination2 *= 1e-6
        elif self.batchIndex2 == 20:
            self.batchStart2 = self.x02
            self.batchDestination2 *= 1e-6
        elif self.batchIndex2 == 21:
            self.batchStart2 = self.z01
            self.batchDestination2 *= 1e-6
        elif self.batchIndex2 == 22:
            self.batchStart2 = self.z02
            self.batchDestination2 *= 1e-6
        elif self.batchIndex2 == 23:
            self.batchStart2 = self.propagationAngle1
            self.batchDestination2 *= (np.pi/180)
        elif self.batchIndex2 == 24:
            self.batchStart2 = self.propagationAngle2
            self.batchDestination2 *= (np.pi/180)
        elif self.batchIndex2 == 25:
            self.batchStart2 = self.polarizationAngle1
            self.batchDestination2 *=(np.pi/180)
        elif self.batchIndex2 == 26:
            self.batchStart2 = self.polarizationAngle2
            self.batchDestination2 *= (np.pi/180)
        elif self.batchIndex2 == 27:
            self.batchStart2 = self.circularity1
        elif self.batchIndex2 == 28:
            self.batchStart2 = self.circularity2
        elif self.batchIndex2 == 29:
            self.batchStart2 = self.crystalTheta
            self.batchDestination2 *= (np.pi/180)
        elif self.batchIndex2 == 30:
            self.batchStart2 = self.crystalPhi
            self.batchDestination2 *= (np.pi/180)
        elif self.batchIndex2 == 31:
            self.batchStart2 = self.nonlinearAbsorptionStrength
        elif self.batchIndex2 == 32:
            self.batchStart2 = self.drudeGamma
            self.batchDestination2 *= 1e12
        elif self.batchIndex2 == 33:
            self.batchStart2 = self.effectiveMass
        elif self.batchIndex2 == 34:
            self.batchStart2 = self.crystalThickness
            self.batchDestination2 *= 1e-6
        elif self.batchIndex2 == 35:
            self.batchStart2 = self.propagationStep
            self.batchDestination2 *= 1e-9
        elif self.batchIndex2 == 36:
            self.batchStart2 = 0
        elif self.batchIndex2 == 37:
            self.batchStart2 = 0
        self.batchVector2 = np.linspace(self.batchStart2,self.batchDestination2,self.Nsims2)

        self.timeVector = self.timeStep*np.arange(0,self.Ntime)
        self.frequencyVector = np.fft.fftfreq(self.Ntime, d=self.timeStep)
        self.frequencyVectorSpectrum = self.frequencyVector[0:self.Nfreq]
        self.frequencyVectorSpectrum[-1] *= -1
        self.spaceVector = self.spatialStep * (np.arange(0,self.Nspace) - self.Nspace/2) + 0.25 * self.spatialStep
        
def fwhm(x: np.ndarray, y: np.ndarray, height: float = 0.5) -> float:
    """
    Gives the full-width at half-maximum of data in a numpy array pair.

    :param x: The x-values (e.g. the scale of the vector; has the same units as the return value)
    :type x: np.ndarray

    :param y: The y-values (to which half-maximum refers)
    :type y: np.ndarray

    :param height: Instead of half-max, can optionally return height*max (e.g. default 0.5)
    :type height: float

    :return: The full-width at half-max (units of x)
    :rtype: float
    """
    heightLevel = np.max(y) * height
    indexMax = np.argmax(y)
    y = np.roll(y, - indexMax + int(np.shape(y)[0]/2),axis=0)
    indexMax = np.argmax(y)
    xLower = np.interp(heightLevel, y[:indexMax], x[:indexMax])
    xUpper = np.interp(heightLevel, np.flip(y[indexMax:]), np.flip(x[indexMax:]))
    return xUpper - xLower

def norma(v: np.ndarray):
    """
    Divide an array by its maximum value.
    
    :param v: the array
    :type v: np.ndarray
    
    :return: the normalized array
    :rtype: np.ndarray
    """
    return v/v.max()

def normaM(v: np.ndarray):
    """
    Normalize the columns of a 2D matrix
    
    :param v: the array
    :type v: np.ndarray
    
    :return: the normalized array
    :rtype: np.ndarray
    """
    out = np.zeros(np.shape(v))
    for i in range(0,np.shape(out)[0]):
        out[i,:] = norma(v[i,:])
    return out

def printSellmeier(sc: np.ndarray, highPrecision=False):
    """
    print an array containing LWE sellmeier coefficients in a format
    that can be copy-pasted into the CrystalDatabase.txt file
    
    :param sc: the coefficients (22-element array)
    :type sc: np.ndarray
    :param highPrecision: if true, use 15 digits for the numbers
    """
    if highPrecision:
        s = np.array2string(sc, formatter={'float_kind': '{0:.15g}'.format}).replace('\n','').replace('[','').replace(']','')
    else:
        s = np.array2string(sc, formatter={'float_kind': '{0:.6g}'.format}).replace('\n','').replace('[','').replace(']','')
    print(s)

def sellmeier(wavelengthMicrons, a: np.ndarray, equationType: int):
    """
    Use the sellmeier coeffiecients in LWE format to produce a refractive index curve.

    :param wavelengthMicrons: the wavelength in microns; can be a float or array of floats
    :param a: 22-element numpy array giving the coefficients
    :param equationType: specify the type of equation (0 -> general fitting function, 1->Lorentzians, 2->Gaussians)
    
    :return: complex refractive index corresponding to the value(s) of wavelengthMicrons
    """
    np.seterr(divide='ignore', invalid='ignore')
    w = 2 * np.pi * 2.99792458e8 / (1e-6*wavelengthMicrons)
    ls = wavelengthMicrons**2
    k = 3182.607353999257
    def rectangularBand(w,w0,width,height):
        if width != 0:
            scaledAxis = (w-w0)/width
        else:
            scaledAxis = (w-w0)
        imagPart = np.zeros(w.size)
        imagPart[np.abs(scaledAxis)<0.5] = -height
        realPart = np.zeros(w.size) + 1.0
        realPart[scaledAxis!=0.5] = -height * np.log(np.abs((scaledAxis+0.5)/(scaledAxis-0.5)))/np.pi
        return realPart + 1j*imagPart
    def gaussianBand(w,w0,width,height):
        if width == 0.0 or height == 0:
            return 0 + 1j*0
        scaledF = (w-w0)/(np.sqrt(2.0) * width)
        realPart = np.zeros(np.shape(scaledF))
        if isinstance(scaledF, np.ndarray):
            dawsonArr = np.vectorize(deviceDawson)
            realPart = -dawsonArr(scaledF)/np.sqrt(np.pi)
        else:
            realPart = -deviceDawson(scaledF)/np.sqrt(np.pi)
        imagPart = np.exp(-scaledF*scaledF)
        return np.abs(height) * (realPart - 1j * imagPart)

    if equationType == 0:
        n = (a[0] + (a[1] + a[2] * ls) / (ls + a[3]) + (a[4] + a[5] * ls) / (ls + a[6]) + (a[7] + a[8] * ls) / (ls + a[9]) + (a[10] + a[11] * ls) / (ls + a[12]) + a[13] * ls + a[14] * ls * ls + a[15] * ls * ls * ls) 
        n[n<0] = 1
        n = n + k * a[16] / ((a[17] - w ** 2) +  (a[18] * w) * 1j)
        n += k * a[19] / ((a[20] - w ** 2) +  (a[21] * w) * 1j)
    elif equationType == 1:
        a = np.abs(a)
        n = a[0] + k * a[1] / ((a[2] - w ** 2) +  (a[3] * w) * 1j)
        n += k * a[4] / ((a[5] - w ** 2) +  (a[6] * w) * 1j)
        n += k * a[7] / ((a[8] - w ** 2) +  (a[9] * w) * 1j)
        n += k * a[10] / ((a[11] - w ** 2) +  (a[12] * w) * 1j)
        n += k * a[13] / ((a[14] - w ** 2) +  (a[15] * w) * 1j)
        n += k * a[16] / ((a[17] - w ** 2) +  (a[18] * w) * 1j)
        n += k * a[19] / ((a[20] - w ** 2) +  (a[21] * w) * 1j)
    elif equationType == 2:
        a = np.abs(a)
        n = a[0]
        for i in range(0,7):
            n += gaussianBand(w,a[i*3+1],a[2 + i*3],a[3+i*3])

    return np.sqrt(n)

def load(filePath: str, loadFieldArray=True):
    """
    A wrapper to the constructor of the lightwaveExplorerResult class. Loads
    The output of a simulation run and stores it in the returned class.

    :param filePath: The path to the .txt file describing the simulation result
    :type filePath: str

    :param loadFieldArray: Set to False in order to not load the electric field
    :type loadFieldArray: bool

    :return: The class contianing the parameters and results
    :rtype: LightwaveExplorerResult
    """
    s = lightwaveExplorerResult(filePath=filePath,loadFieldArray=loadFieldArray)
    return s

def getRII_object(url):
    """
    Load a yaml file from a URL, such as what one finds on refractiveindex.info
    :param url: The address of the yaml file
    :type url: str

    :return: the yaml file
    """
    riiurl = urllib.request.urlopen(url)
    return  yaml.safe_load(riiurl)

def getSellmeierFromRII(url):
    """
    Get the sellmeier equation of a material on refractiveindex.info
    
    :param url: The address of the yaml file
    :type url: str

    :return: The 22-element array containing the sellmeier coefficients
    """
    RIIobj = getRII_object(url)
    types = np.array([x["type"] for x in RIIobj["DATA"]])
    retrievedCoeffs = np.zeros(22)

    if 'formula 1' in types:
        firstTrue = ((types=='formula 2').cumsum().cumsum()==1).argmax()
        RIIcoeffs = np.fromstring(RIIobj["DATA"][firstTrue]["coefficients"], dtype=float, sep=' ')
        Nresonances = int(np.floor((RIIcoeffs.size-1)/2))
        retrievedCoeffs[0] = RIIcoeffs[0] + 1
        for i in range(0,min(7,Nresonances)):
            retrievedCoeffs[i*3 + 2] = RIIcoeffs[1 + 2*i]
            retrievedCoeffs[i*3 + 3] = -(RIIcoeffs[2 + 2*i]**2)
    elif 'formula 2' in types:
        firstTrue = ((types=='formula 2').cumsum().cumsum()==1).argmax()
        RIIcoeffs = np.fromstring(RIIobj["DATA"][firstTrue]["coefficients"], dtype=float, sep=' ')
        Nresonances = int(np.floor((RIIcoeffs.size-1)/2))
        retrievedCoeffs[0] = RIIcoeffs[0] + 1
        for i in range(0,min(7,Nresonances)):
            retrievedCoeffs[i*3 + 2] = RIIcoeffs[1 + 2*i]
            retrievedCoeffs[i*3 + 3] = -RIIcoeffs[2 + 2*i]
    elif 'formula 4' in types:
        firstTrue = ((types=='formula 4').cumsum().cumsum()==1).argmax()
        RIIcoeffs = np.fromstring(RIIobj["DATA"][firstTrue]["coefficients"], dtype=float, sep=' ')
        Nresonances = int(np.floor((RIIcoeffs.size-1)/4))
        retrievedCoeffs[0] = RIIcoeffs[0]
        for i in range(0,min(Nresonances,2)):
            if RIIcoeffs[2 + 4*i] == 0:
                retrievedCoeffs[i*3 + 1] = RIIcoeffs[1 + 4*i]
            else:
                retrievedCoeffs[i*3 + 2] = RIIcoeffs[1 + 4*i]
            retrievedCoeffs[i*3 + 3] = -(RIIcoeffs[3 + 4*i]**RIIcoeffs[4+4*i])
        if RIIcoeffs.size > 5:
            Npoly = int(np.floor(int(RIIcoeffs.size - 5)/2))
            for i in range(0,Npoly):
                if RIIcoeffs[5 + 2*i + 1] == 2.0:
                    retrievedCoeffs[13] = RIIcoeffs[5 + 2*i]
                if RIIcoeffs[5 + 2*i + 1] == 4.0:
                    retrievedCoeffs[14] = RIIcoeffs[5 + 2*i]
                if RIIcoeffs[5 + 2*i + 1] == 6.0:
                    retrievedCoeffs[15] = RIIcoeffs[5 + 2*i]
    else:
        print("Sorry, this formula hasn't been implemented yet.")
    return retrievedCoeffs

def getTabulatedDataFromRII(url):
    """
    Get a table of (possibly complex) refractive index values from refractiveindex.info
    
    :param url: the address of the yaml file on the website
    :type url: str

    :return: Array containing the retrieved values
    """
    RIIobj = getRII_object(url)
    types = np.array([x["type"] for x in RIIobj["DATA"]])
    if 'tabulated nk' in types:
        firstTrue = ((types=='tabulated nk').cumsum().cumsum()==1).argmax()
        nkData = np.array([np.array(i.split(' ')).astype(float) for i in str(RIIobj["DATA"][firstTrue]["data"]).strip().split('\n')])
    elif 'tabulated k' in types:
        firstTrue = ((types=='tabulated k').cumsum().cumsum()==1).argmax()
        kData = np.array([np.array(i.split(' ')).astype(float) for i in str(RIIobj["DATA"][firstTrue]["data"]).strip().split('\n')])
        nkData = np.zeros((kData[:,0].size, 3))
        nkData[:,0] = kData[:,0]
        nkData[:,2] = kData[:,1]
        sellCoeffs = getSellmeierFromRII(url)
        nkData[:,1] = np.real(sellmeier(nkData[:,0],sellCoeffs,0))
    elif 'tabulated n' in types:
        firstTrue = ((types=='tabulated n').cumsum().cumsum()==1).argmax()
        nData = np.array([np.array(i.split(' ')).astype(float) for i in str(RIIobj["DATA"][firstTrue]["data"]).strip().split('\n')])
        nkData = np.zeros((kData[:,0].size, 3))
        nkData[:,0] = nData[:,0]
        nkData[:,1] = nData[:,1]

    return nkData
        

def EOS(s: lightwaveExplorerResult, bandpass=None, filterTransmissionNanometers=None, detectorResponseNanometers=None):
    """
    Takes a result of a calculation and extracts the electro-optic sampling signal
    The simulation must be done in a way that includes mixing of the signal and local oscillator
    either by fully simulating the waveplate, or by rotating the system of coordinates in
    a sequence (by calling rotate(45))

    The spectral response of the detection system can be adjusted in three ways:
    1: application of a supergaussian bandpass filter with a three element list:
    bandpass=[centralFrequency, sigma, superGaussianOrder]
    2: application of a measured transmission of the filters and beamline optics:
    filterTransmissionNanometers = np.array([wavelengthsInNanometers, transmissionIntensity])
    3: application of the detector's spectral response (assumed identical for the two photodiodes)
    same format as 2

    :param s: The loaded simulation result
    :param bandpass: supergaussian bandpass filter with a three element list:
    bandpass=[centralFrequency, sigma, superGaussianOrder]
    :param filterTransmissionNanometers: measured transmission of the filters and beamline optics:
    filterTransmissionNanometers = np.array([wavelengthsInNanometers, transmissionIntensity])
    :param detectorResponseNanometers: detector response function, in the same format as filterTransmissionNanometers

    :return: The signal vs. delay of the EOS measurement.
    """
    c = 2.99792458e8
    totalResponse = 1.

    #make everything numpy arrays
    bandpass = np.array(bandpass)
    filterTransmissionNanometers = np.array(filterTransmissionNanometers)
    detectorResponseNanometers = np.array(detectorResponseNanometers)

    #resolve the various filters
    if bandpass.any() != None:
        bandpassFilter = np.exp(-(s.frequencyVectorSpectrum-bandpass[0])**bandpass[2]/(2*bandpass[1]**bandpass[2]))
        totalResponse *= bandpassFilter

    if filterTransmissionNanometers.any() != None:
        sortIndicies = np.argsort(1e9*c/filterTransmissionNanometers[0,:])
        dataFrequencyAxis = np.array([1e9*c/filterTransmissionNanometers[0,sortIndicies], filterTransmissionNanometers[1,sortIndicies]])
        totalResponse  *= np.interp(s.frequencyVectorSpectrum, dataFrequencyAxis[0,:], dataFrequencyAxis[1,:])
    
    if detectorResponseNanometers.any() != None:
        sortIndicies = np.argsort(1e9*c/detectorResponseNanometers[0,:])
        dataFrequencyAxis = np.array([1e9*c/detectorResponseNanometers[0,sortIndicies], detectorResponseNanometers[1,sortIndicies]])
        totalResponse  *= np.interp(s.frequencyVectorSpectrum, dataFrequencyAxis[0,:], dataFrequencyAxis[1,:])

    #EOS signal is the integral of the difference between the two spectra, multiplied by the total spectral response
    if s.Nsims2>1:
        EOSsignal = np.array([np.sum((totalResponse*(np.squeeze(s.spectrum_x[i,:,:]-s.spectrum_y[i,:,:]))), axis=1) for i in range(s.Nsims2)])
    else:
        EOSsignal = np.sum((totalResponse*(s.spectrum_x-s.spectrum_y)), axis=1)
    return EOSsignal

def sellmeierFit(wavelengthMicrons, startingCoefficients, activeElements: np.array, eqnType: int, nTarget, imaginaryWeight):
    """
    Fit a set of sellmeier coefficents to measured data.
    
    :param wavelengthMicrons: array of wavelengths
    :param startingCoeffiecients: starting point of the coefficients, 22-element numpy array of floats
    :param activeElements: array of indexes of the elements that may be adjusted
    :param eqnType: type of Sellmeier equation (0=general fitting, 1=lorentzians, 2=gaussians)
    :param nTarget: refractive index curve to fit to (same size as wavelengthMicrons)
    :param imaginaryWeight: factor by which to change the weighting of the imaginary part of the refractive index
    """
    fitImaginary = imaginaryWeight != 0
    def expandCoeffs(x):
        x1 = np.array(startingCoefficients)
        for i in range(0,activeElements.size):
            x1[activeElements[i]] = x[i]
        return x1
    def fun_nforx(x):
        return sellmeier(wavelengthMicrons, expandCoeffs(x), eqnType)

    def fun_residual(x):
        nx = fun_nforx(x)
        if fitImaginary:
            returnVals = 1e3*np.append(np.real(nTarget - nx), np.real(imaginaryWeight*(np.sqrt(-(np.imag(nTarget))) - np.sqrt(-(np.imag(nx))))))
        else:
            returnVals = 1e3*np.real(nTarget - nx)
        return returnVals

    res = least_squares(fun_residual, startingCoefficients[activeElements], gtol=None, xtol=None, ftol = 1e-12, max_nfev=16384)
    
    if (eqnType == 1) or (eqnType == 2):
        res.x = np.abs(res.x)
    print("Resulting coefficients:")
    printSellmeier(expandCoeffs(res.x))

    return expandCoeffs(res.x), fun_nforx(res.x)

#Get the plasma density associated with a field using the ionization model in the simulation
def getPlasmaDensityAndCurrent(E, dt, pulseFrequency, scoeffs, bandGap, effectiveMass, NLabsorption, gamma):
    """
    Get the plasma current associated with a field and set of parameters. This is just for testing,
    I wouldn't recommend using it for anything yet....
    """
    #get the refractive index of the crystal
    f = np.fft.fftfreq(E.size,dt)
    lam = np.array(f)
    for i in range(0,lam.size):
        if f[i] != 0:
            lam[i] = np.abs(2.99792458e8/f[i])
        else:
            lam[i] = 0.0
    n = np.real(sellmeier(lam*1e6, scoeffs, 0))
    
    #calculate chi1
    chi1 = n**2 - 1.0
    chi1[chi1<0.0] = 0
    chi1[np.isnan(chi1)]=0.0

    #plasma generation constants
    plasmaParam2 = 2.817832e-8 / (1.6022e-19 * bandGap * effectiveMass)
    pMax = np.ceil(bandGap * 241.79893e12 / pulseFrequency) - 2
    fieldFactor = 1.0/(chi1 + 1)**0.25

    #get the linear polarization for applying millers rule to the dispersion of the absorption cross section
    Pol1 = np.real(np.fft.ifft(fieldFactor*chi1*np.fft.fft(E)))
    Esquared = NLabsorption* (Pol1**2)

    #Jx starts at the absorption current; e.g. the one responsible for the removal of energy from the field
    #as carriers are generated
    Jx = Pol1 * (Esquared**(pMax))

    #number of carriers is assumed to be equal to the energy removed from the field/bandgap
    #Rate of power loss of the field is E*J
    Ncarriers =  dt * np.cumsum(plasmaParam2 * Jx * Pol1)

    #integrate damped drude response to fill in the rest of the current
    integralx = 0.0
    for i in range(0, E.size):
        expGammaT = np.exp(dt * i * gamma)
        expMinusGammaT = np.exp(-dt * i * gamma)
        integralx += Ncarriers[i] * expGammaT * E[i]
        Jx[i] += expMinusGammaT * integralx

    return Ncarriers, dt*Jx

def deviceDawson(x):
        """
        replica of the dawson function used in the c++ code
        should provide results similar to the scipy dawson function
        
        :param x: argument of the dawson function
        :returns: F(x), the dawson function at x
        """

		#parameters determining accuracy (higher n, smaller h -> more accurate but slower)
        n = 15
        h = 0.3

        #series expansion for small x
        if abs(x) < 0.2:
            x2 = x * x
            x4 = x2 * x2
            return x * (1.0 - 2.0 * x2 / 3.0 + 4.0 * x4 / 15.0 - 8.0 * x2 * x4 / 105.0 + (16.0 / 945) * x4 * x4 - (32.0 / 10395) * x4 * x4 * x2)


        n0 = 2 * (int)(round(0.5 * x / h))
        x0 = h * n0
        xp = x - x0
        d = 0.0
        for i in range (-n,n):
            if (i % 2 != 0):
                d += np.exp(-(xp - i * h) * (xp - i * h)) / (i + n0)
            

        return d/np.sqrt(np.pi)

def loadSplit(baseName: str, Ntotal: int, batchType:str):
    """
    load a set of single simulations and fuse the results together as
    if they came from a batch. May be useful for getting around memory
    limitations.

    :param listOfFileNames: list of strings containing the file names to load, in order
    :param batchType: the attribute being scanned in the batch, e.g. frequency1
    """
    listOfFileNames = [f"{baseName}{i:04d}.txt" for i in range(Ntotal)]
    baseStructure = load(listOfFileNames[0])
    stackAxis = len(baseStructure.Ext_x.shape)
    if stackAxis == 2:
        tmp = np.array(baseStructure.Ext_x)
        baseStructure.Ext_x = np.zeros((baseStructure.Ext_x.shape[0],baseStructure.Ext_x.shape[1],Ntotal), dtype=float)
        baseStructure.Ext_x[:,:,0] = tmp
        tmp = np.array(baseStructure.Ext_y)
        baseStructure.Ext_y = np.zeros(baseStructure.Ext_x.shape,dtype=float)
        baseStructure.Ext_y[:,:,0] = tmp
    else:
        tmp = np.array(baseStructure.Ext_x)
        baseStructure.Ext_x = np.zeros((baseStructure.Ext_x.shape[0],baseStructure.Ext_x.shape[1],baseStructure.Ext_x.shape[2],Ntotal), dtype=float)
        baseStructure.Ext_x[:,:,:,0] = tmp
        tmp = np.array(baseStructure.Ext_y)
        baseStructure.Ext_y = np.zeros(baseStructure.Ext_x.shape,dtype=float)
        baseStructure.Ext_y[:,:,:,0] = tmp
    tmp = np.array(baseStructure.spectrum_x)
    baseStructure.spectrum_x = np.zeros((Ntotal,baseStructure.spectrum_x.shape[0]),dtype=float)#baseStructure.spectrum_x[np.newaxis,:]
    baseStructure.spectrum_x[0,:] = tmp
    tmp = np.array(baseStructure.spectrum_y)
    baseStructure.spectrum_y = np.zeros(baseStructure.spectrum_x.shape,dtype=float)
    baseStructure.spectrum_y[0,:] = tmp
    tmp = np.array(baseStructure.spectrumTotal)
    baseStructure.spectrumTotal = np.zeros(baseStructure.spectrum_x.shape,dtype=float)
    baseStructure.spectrumTotal[0,:] = tmp

    baseStructure.batchVector = getattr(baseStructure, batchType)
    baseStructure.batchStart = baseStructure.batchVector
    
    for i in range(1,Ntotal):
        newStructure = load(listOfFileNames[i])
        if stackAxis == 2:
            baseStructure.Ext_x[:,:,i] = newStructure.Ext_x
            baseStructure.Ext_y[:,:,i] = newStructure.Ext_y
        else:
            baseStructure.Ext_x[:,:,:,i] = newStructure.Ext_x
            baseStructure.Ext_y[:,:,:,i] = newStructure.Ext_y
        baseStructure.spectrum_x[i,:] = newStructure.spectrum_x
        baseStructure.spectrum_y[i,:] = newStructure.spectrum_y
        baseStructure.spectrumTotal[i,:] = newStructure.spectrumTotal
        baseStructure.batchVector = np.append(baseStructure.batchVector, getattr(baseStructure, batchType))
    
    return baseStructure

def fuseBinaries(outputTextFile: str):
    """
    Combine the binary components of a simulation that was split to run on a cluster.
    
    :param inputTextFile: The base file name associated with the simulation. If this is Result.Txt, it will
    combine the files associated with Result0000.txt, Result0001.txt and so on
    """
    def fuseFile(baseName: str, ending: str):

        output_name = baseName+ending
        if os.path.exists(output_name):
            os.remove(output_name)
        print("Fusing "+output_name+" from:")
        files = [filename for filename in os.listdir() if filename.startswith(baseName) and filename.endswith(ending)]
        files.sort()
        print(files)
        output = open(output_name,'wb')
        for file in files:
            current = open(file,'rb')
            try:
                while True:
                    piece = current.read(1024*1024*128)
                    if not piece:
                        break
                    output.write(piece)
            finally:
                current.close()
                print(file)
        output.close()
    
    base = os.path.splitext(os.path.basename(outputTextFile))[0]

    fuseFile(base,"_Ext.dat")
    fuseFile(base,"_spectrum.dat")

def fuseZips(outputFile: str):
    """
    Combine the zip files resulting from a simulation that was split to run on a cluster
    
    :param outputFile: The zip file created to run on the cluster. If this is Result.zip, it will
    combine the files Result00000.zip, Result00001.zip and so on
    """
    ending = ".zip"
    baseName = os.path.splitext(os.path.basename(outputFile))[0]
    destination = os.path.splitext(outputFile)[0]+ending
    files = sorted([filename for filename in os.listdir() if filename.startswith(baseName) and filename.endswith(ending) and filename != destination])
    print(files)
    print(destination)
    with zipfile.ZipFile(destination,'a',compression=8) as destinationZip:
        Ext = tempfile.NamedTemporaryFile(delete=False)
        spectrum = tempfile.NamedTemporaryFile(delete=False)
        for sourceFile in files:
            currentBase = os.path.splitext(os.path.basename(sourceFile))[0]
            print(currentBase)
            with zipfile.ZipFile(sourceFile,'r') as sourceZip:
                spectrum.write(sourceZip.read(currentBase+"_spectrum.dat"))
                spectrum.flush()
                Ext.write(sourceZip.read(currentBase+"_Ext.dat"))
                Ext.flush()
        destinationZip.write(spectrum.name, baseName+"_spectrum.dat")
        destinationZip.write(Ext.name, baseName+"_Ext.dat")
    Ext.close()
    spectrum.close()
    os.unlink(Ext.name)
    os.unlink(spectrum.name)

