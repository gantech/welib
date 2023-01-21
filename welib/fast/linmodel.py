""" 
Tools to extract a linear model from OpenFAST


"""

##
import numpy as np
import pandas as pd
import copy
import os
import matplotlib.pyplot as plt

# Local
import welib.weio as weio

from welib.fast.tools.lin import * # backward compatibility
from welib.fast.tools.lin import matToSIunits, renameList

from welib.system.statespacelinear import LinearStateSpace
from welib.yams.windturbine import FASTWindTurbine


DEFAULT_COL_MAP_LIN ={
  'psi_rot_[rad]'       : 'psi'      ,
  'Azimuth_[rad]'       : 'psi'      ,
  'RotSpeed_[rad/s]'    : 'dpsi'     ,
  'd_psi_rot_[rad/s]'   : 'dpsi'     ,
  'qt1FA_[m]'           : 'q_FA1'    ,
  'd_qt1FA_[m/s]'       : 'dq_FA1'   ,
  'd_PtfmSurge_[m/s]'   : 'dx'       ,
  'd_PtfmSway_[m/s]'    : 'dy'       ,
  'd_PtfmHeave_[m/s]'   : 'dz'       ,
  'd_PtfmRoll_[rad/s]'  : 'dphi_x'   ,
  'd_PtfmPitch_[rad/s]' : 'dphi_y'   ,
  'd_PtfmYaw_[rad/s]'   : 'dphi_z'   ,
  'PtfmSurge_[m]'       : 'x'        ,
  'PtfmSway_[m]'        : 'y'        ,
  'PtfmHeave_[m]'       : 'z'        ,
  'PtfmRoll_[rad]'      : 'phi_x'    ,
  'PtfmPitch_[rad]'     : 'phi_y'    ,
  'PtfmYaw_[rad]'       : 'phi_z'    ,
  'NcIMUTAxs_[m/s^2]'   : 'NcIMUAx'   ,
  'NcIMUTAys_[m/s^2]'   : 'NcIMUAy'   ,
  'NcIMUTAzs_[m/s^2]'   : 'NcIMUAz'   ,
  'NcIMUTVxs_[m/s]'     : 'NcIMUVx'   ,
  'NcIMUTVys_[m/s]'     : 'NcIMUVy'   ,
  'NcIMUTVzs_[m/s]'     : 'NcIMUVz'   ,
  'BPitch1_[rad]'       : 'pitchB1'    , # Also B1Pitch_[rad]
  'PitchColl_[rad]'     : 'pitch'    , # Also B1Pitch_[rad]
  'Qgen_[Nm]'           : 'Qgen'     ,
  'HubFxN1_[N]'         : 'Thrust'   ,
  'HubFyN1_[N]'         : 'fay'   ,
  'HubFzN1_[N]'         : 'faz'   ,
  'HubMxN1_[Nm]'        : 'Qaero'    , 
  'HubMyN1_[Nm]'        : 'may'      , 
  'HubMzN1_[Nm]'        : 'maz'      , 
  'PtfmFxN1_[N]'        : 'fhx'      ,
  'PtfmFyN1_[N]'        : 'fhy'      ,
  'PtfmFzN1_[N]'        : 'fhz'      ,
  'PtfmMxN1_[Nm]'       : 'mhx'      ,
  'PtfmMyN1_[Nm]'       : 'mhy'      ,
  'PtfmMzN1_[Nm]'       : 'mhz'      ,
  'Q_Sg_[m]'        : 'x',
  'Q_Sw_[m]'        : 'y',
  'Q_Hv_[m]'        : 'z',
  'Q_R_[rad]'       : 'phi_x',
  'Q_P_[rad]'       : 'phi_y',
  'Q_Y_[rad]'       : 'phi_z',
  'QD_Sg_[m/s]'     : 'dx',
  'QD_Sw_[m/s]'     : 'dy',
  'QD_Hv_[m/s]'     : 'dz',
  'QD_R_[rad/s]'    : 'dphi_x'   ,
  'QD_P_[rad/s]'    : 'dphi_y'   ,
  'QD_Y_[rad/s]'    : 'dphi_z'   ,
  'QD2_Sg_[m/s^2]'  : 'ddx',
  'QD2_Sw_[m/s^2]'  : 'ddy',
  'QD2_Hv_[m/s^2]'  : 'ddz',
  'QD2_R_[rad/s^2]' : 'ddphi_x'   ,
  'QD2_P_[rad/s^2]' : 'ddphi_y'   ,
  'QD2_Y_[rad/s^2]' : 'ddphi_z'   ,
  'NacYaw_[rad]'    : 'yaw',
#           'NacFxN1_[N]'       : 'fnx'   ,
#           'NacMxN1_[N]'       : 'mnx'    , 
#    Qgen_[Nm]  HubFxN1_[N]  HubFyN1_[N]  HubFzN1_[N] 
#               NacFxN1_[N]  NacFyN1_[N]  NacFzN1_[N]
}


DEFAULT_COL_MAP_OF ={
#   'NcIMUTAxs_[m/s^2]'   : 'TTIMUx'   ,
#   'NcIMUTAys_[m/s^2]'   : 'TTIMUy'   ,
#   'NcIMUTAzs_[m/s^2]'   : 'TTIMUz'   ,
#   'BPitch1_[rad]'       : 'pitchB1'    , # Also B1Pitch_[rad]
#   'PitchColl_[rad]'     : 'pitch'    , # Also B1Pitch_[rad]
#   'Qgen_[Nm]'           : 'Qgen'     ,
#   'HubFxN1_[N]'         : 'Thrust'   ,
#   'HubFyN1_[N]'         : 'fay'   ,
#   'HubFzN1_[N]'         : 'faz'   ,
#   'HubMxN1_[Nm]'        : 'Qaero'    , 
#   'HubMyN1_[Nm]'        : 'may'      , 
#   'HubMzN1_[Nm]'        : 'maz'      , 
  'FxhO_[N]'        : 'fhx'      ,
  'FyhO_[N]'        : 'fhy'      ,
  'FzhO_[N]'        : 'fhz'      ,
  'MxhO_[Nm]'       : 'mhx'      ,
  'MyhO_[Nm]'       : 'mhy'      ,
  'MzhO_[Nm]'       : 'mhz'      ,
  'PtfmSurge_[m]'       : 'x'        ,
  'PtfmSway_[m]'        : 'y'        ,
  'PtfmHeave_[m]'       : 'z'        ,
  'PtfmRoll_[rad]'      : 'phi_x'    ,
  'PtfmPitch_[rad]'     : 'phi_y'    ,
  'PtfmYaw_[rad]'       : 'phi_z'    ,
  'Q_Sg_[m]'        : 'x',
  'Q_Sw_[m]'        : 'y',
  'Q_Hv_[m]'        : 'z',
  'Q_R_[rad]'       : 'phi_x',
  'Q_P_[rad]'       : 'phi_y',
  'Q_Y_[rad]'       : 'phi_z',
  'Q_TFA1_[m]'      : 'q_FA1',
  'Q_TSS1_[m]'      : 'q_FA1',
  'Q_TFA2_[m]'      : 'q_FA2',
  'Q_TSS2_[m]'      : 'q_SS2',
  'Q_Yaw_[m]'       : 'yaw',
  'NacYaw_[rad]'    : 'yaw',
  'Azimuth_[rad]'   : 'psi'      ,
  'Q_DrTr_[rad]'    : 'nu'   ,
  'QD_Sg_[m/s]'     : 'dx',
  'QD_Sw_[m/s]'     : 'dy',
  'QD_Hv_[m/s]'     : 'dz',
  'QD_R_[rad/s]'    : 'dphi_x'   ,
  'QD_P_[rad/s]'    : 'dphi_y'   ,
  'QD_Y_[rad/s]'    : 'dphi_z'   ,
  'QD_TFA1_[m/s]'   : 'dq_FA1',
  'QD_TSS1_[m/s]'   : 'dq_FA1',
  'QD_TFA2_[m/s]'   : 'dq_FA2',
  'QD_TSS2_[m/s]'   : 'dq_SS2',
  'QD_Yaw_[rad/s]'  : 'dyaw',
  'RotSpeed_[rad/s]': 'dpsi',
  'Q_DrTr_[rad/s]'  : 'dnu'   ,
  'QD_GeAz_[rad/s]' : 'dpsi',
  'QD2_Sg_[m/s^2]'  : 'ddx',
  'QD2_Sw_[m/s^2]'  : 'ddy',
  'QD2_Hv_[m/s^2]'  : 'ddz',
  'QD2_R_[rad/s^2]' : 'ddphi_x'   ,
  'QD2_P_[rad/s^2]' : 'ddphi_y'   ,
  'QD2_Y_[rad/s^2]' : 'ddphi_z'   ,
  'QD2_TFA1_[m/s^2]': 'ddq_FA1',
  'QD2_TSS1_[m/s^2]': 'ddq_FA1',
  'QD2_TFA2_[m/s^2]': 'ddq_FA2',
  'QD2_TSS2_[m/s^2]': 'ddq_SS2',
  'QD2_Yaw_[rad/s^2]': 'ddyaw',
  'QD2_GeAz_[rad/s^2]': 'ddpsi',
  'QD2_DrTr_[rad/s^2]': 'ddnu',
  'Q_B1F1_[m]': 'q_B1Fl1',
  'Q_B1F2_[m]': 'q_B1Fl2',
  'Q_B1E1_[m]': 'q_B1Ed1',
}



def _loadOFOut(filename, tMax=None, zRef=None):
    ext = os.path.splitext(filename)[1].lower()
    if ext=='.fst':
        if os.path.exists(filename.replace('.fst','.outb')): 
            outfile=filename.replace('.fst','.outb')
        elif os.path.exists(filename.replace('.fst','.out')): 
            outfile=filename.replace('.fst','.out')
        else:
            raise Exception('Cannot find an OpenFAST output file near: {}'.format(filename))
    else:
        outfile=filename
    print('FASTLinModel: loading OF :', outfile)
    dfFS = weio.read(outfile).toDataFrame()
    if tMax is not None:
        dfFS=dfFS[dfFS['Time_[s]']<tMax]
    time =dfFS['Time_[s]'].values

    # Remove duplicate
    dfFS = dfFS.loc[:,~dfFS.columns.duplicated()].copy()

    # --- Convert hydro loads to loads at zref
    #if zRef is not None:
    #    from welib.FEM.utils import transferRigidLoads
    #    from welib.yams.utils import transferLoadsZPoint
    #    P_HDRef = np.array((0,0,0))
    #    P_EDRef = np.array((0,0,zRef))
    #    # Input loads are at the body origin (ED ref point)
    #    cols = ['HydroFxi_[N]', 'HydroFyi_[N]', 'HydroFzi_[N]', 'HydroMxi_[N-m]', 'HydroMyi_[N-m]', 'HydroMzi_[N-m]']
    #    if 'Q_R_[rad]' in dfFS.columns:
    #        vphi_x = dfFS['Q_R_[rad]']
    #    else:
    #        vphi_x = dfFS['PtfmRoll_[deg]'].values*np.pi/180
    #    if 'Q_P_[rad]' in dfFS.columns:
    #        vphi_y = dfFS['Q_P_[rad]']
    #    else:
    #        vphi_y = dfFS['PtfmPitch_[deg]'].values*np.pi/180
    #    if 'Q_Y_[rad]' in dfFS.columns:
    #        vphi_z = dfFS['Q_Y_[rad]']
    #    else:
    #        vphi_z = dfFS['PtfmYaw_[deg]'].values*np.pi/180
    #    M = dfFS[cols].values
    #    MT = transferLoadsZPoint(M.T, zRef, vphi_x, vphi_y, vphi_z, rot_type='default').T
    #    cols = ['FxhO_[N]', 'FyhO_[N]', 'FzhO_[N]', 'MxhO_[Nm]', 'MyhO_[Nm]', 'MzhO_[Nm]']
    #    dfHydro = pd.DataFrame(data=MT, columns=cols)
    #    dfFS = pd.concat((dfFS, dfHydro), axis=1)

    return dfFS, time

# --------------------------------------------------------------------------------}
# --- Class to handle a linear model from OpenFAST
# --------------------------------------------------------------------------------{
class FASTLinModel(LinearStateSpace):

    def __init__(self, fstFilename=None, linFiles=None, pickleFile=None, usePickle=False):
        # Init parent class
        LinearStateSpace.__init__(self)
        # --- DATA
        self.WT          = None
        self.fstFilename = fstFilename
        self.dfFS        = None
        self.df          = None

        if usePickle:
            if fstFilename is None:
                raise Exception('Provide an fstFilename to figure out the pickle file')
            self.fstFilename = fstFilename
            if os.path.exists(self.defaultPickleFile):
                self.load()
                return

        if pickleFile is not None:
            # Load pickle File
            self.load(pickleFile)

        elif linFiles is not None:
            # Load all the lin File
            A, B, C, D, xop, uop, yop, sX, sU, sY = self.loadLinFiles(linFiles)
            LinearStateSpace.__init__(self, A=A, B=B, C=C, D=D, q0=xop,
                    sX=sX, sU=sU, sY=sY,
                    verbose=False)

        elif fstFilename is not None:
            # 
            linFiles = [os.path.splitext(fstFilename)[0]+'.1.lin']
            A, B, C, D, xop, uop, yop, sX, sU, sY = self.loadLinFiles(linFiles)
            LinearStateSpace.__init__(self, A=A, B=B, C=C, D=D, q0=xop,
                    sX=sX, sU=sU, sY=sY,
                    verbose=False)
        else:
            raise Exception('Input some files')

        if fstFilename is not None:
            print('FASTLinModel: loading WT :',fstFilename)
            self.WT = FASTWindTurbine(fstFilename)
            self.fstFilename     = fstFilename

        # Set A, B, C, D to SI units
        self.toSI(verbose=False)


    def loadLinFiles(self, linFiles):
        from welib.fast.FASTLin import FASTLin # TODO rename me
        FL = FASTLin(linfiles=linFiles)
        A, B, C, D    = FL.average(WS = None)
        xop, uop, yop = FL.averageOP(WS = None)
        sX, sU, sY = FL.xdescr, FL.udescr, FL.ydescr
        return A, B, C, D, xop, uop, yop, sX, sU, sY

    def rename(self, colMap=None, verbose=False):
        """ Rename labels """
        if colMap is None:
            colMap = DEFAULT_COL_MAP_LIN
        LinearStateSpace.rename(self, colMap=colMap, verbose=verbose)

    def setupSimFromOF(self, outFile=None, fstFilename=None, tMax=None, rename=True, colMap=None, **kwargs):

        # --- Load turbine config
        if fstFilename is not None:
            print('FASTLinModel: loading WT :',fstFilename)
            self.WT_sim = FASTWindTurbine(fstFilename)
            self.fstFilename_sim = fstFilename 
        else:
            self.WT_sim = self.WT
            self.fstFilename_sim = self.fstFilename 

        # --- Load Reference simulation
        #zRef =  -self.p['z_OT'] 
        zRef = - self.WT_sim.twr.pos_global[2]  
        if outFile is None:
            self.dfFS, self.time = _loadOFOut(self.fstFilename_sim, tMax, zRef)
        else:
            self.dfFS, self.time = _loadOFOut(outFile, tMax, zRef)

        # --- Scale to SI
        self.dfFS = matToSIunits(self.dfFS, 'dfOF', verbose=False, row=False)

        # --- Rename
        if rename:
            if colMap is None:
                colMap = DEFAULT_COL_MAP_OF
            self.dfFS.columns = renameList(list(self.dfFS.columns), colMap, False)
            # Remove duplicate
            self.dfFS = self.dfFS.loc[:,~self.dfFS.columns.duplicated()].copy()



        # --- Initial inputs to zero
        self._zeroInputs()


        # --- Initial conditions (Non-linear)!
        q0 = self.WT.z0
        self.q0_NL = q0[self.sX]

        # --- Initial parameters
        #if self.modelName[0]=='B':
        #    self.p = self.WT.yams_parameters(flavor='onebody',**kwargs)
        #else:
        #    self.p = self.WT.yams_parameters(**kwargs)

        return self.time, self.dfFS #, self.p

    def _zeroInputs(self):
        """ 
        u:   dictionary of functions of time
        uop: dictionary
        du : nu x nt array, time series of time
        """
        # Examples of su: T_a, M_y_a M_z_a F_B

        nu = len(self.sU)
        # --- linear inputs "u" is a "du"
        #u=dict()
        #for su in self.sU:
        #    u[su] = lambda t, q=None: 0  # NOTE: qd not supported yet
        #    #u[su] = lambda t, q=None, qd=None: 0  # Setting inputs as zero as funciton of time

        #uop=dict() # Inputs at operating points
        #for su in self.sU:
        #    uop[su] = 0  # Setting inputs as zero as function of time

        u = np.zeros((nu, len(self.time))) # Zero for all time

        # --- Steady State states
        #qop  = None
        qdop  = None

        # --- Store in class
        # equivalent to: self.setInputTimeSeries(self.time, u)
        self.setInputTimeSeries(self.time, u)

        #self.du  = du
        #self.uop = uop
        self.qop = self.qop_default
        #self.qdop = qdop

    @property
    def qop_default(self):
        return pd.Series(np.zeros(len(self.sX)), index=self.sX)

    def plotCompare(self, export=False, nPlotCols=2, prefix='', fig=None, figSize=(12,10), title=''):
        """ 
        NOTE: taken from simulator. TODO harmonization
        """
        from welib.tools.colors import python_colors
        # --- Simple Plot
        dfLI = self.df
        dfFS = self.dfFS
        if dfLI is None and dfFS is None:
            df = dfFS
        else:
            df = dfLI

        if fig is None:
            fig,axes = plt.subplots(int(np.ceil((len(df.columns)-1)/nPlotCols)), nPlotCols, sharey=False, sharex=True, figsize=figSize)
        else:
            axes=fig.axes
            assert(len(axes)>0)
        if nPlotCols==2:
            fig.subplots_adjust(left=0.07, right=0.98, top=0.955, bottom=0.05, hspace=0.20, wspace=0.20)
        else:
            fig.subplots_adjust(left=0.07, right=0.98, top=0.955, bottom=0.05, hspace=0.20, wspace=0.33)
        for i,ax in enumerate((np.asarray(axes).T).ravel()):
            if i+1>=len(df.columns):
                continue
            chan=df.columns[i+1]
            if dfLI is not None:
                if chan in dfLI.columns:
                    ax.plot(dfLI['Time_[s]'], dfLI[chan], '--' , label='linear', c=python_colors(1))
                else:
                    print('Missing column in Lin: ',chan)
            if dfFS is not None:
                if chan in dfFS.columns:
                    ax.plot(dfFS['Time_[s]'], dfFS[chan], 'k:' , label='OpenFAST')
                else:
                    print('Missing column in OpenFAST: ',chan)
            ax.set_xlabel('Time [s]')
            ax.set_ylabel(chan)
            ax.tick_params(direction='in')
            if i==0:
                ax.legend()

        # Scale axes if tiny range
        for i,ax in enumerate((np.asarray(axes).T).ravel()):
            mi, mx = ax.get_ylim()
            mn = (mx+mi)/2
            if np.abs(mx-mn)<1e-6:
                ax.set_ylim(mn-1e-5, mn+1e-5)
        fig.suptitle(title)

        if export:
            fig.savefig(self.fstFilename.replace('.fst','{}_linModel.png'.format(prefix)))

        return fig

    @property
    def defaultPickleFile(self):
        if self.fstFilename is None:
            raise NotImplementedError('Default pickle with no fstFilename')
        return self.fstFilename.replace('.fst','_linModel.pkl')

    def save(self, pickleFile=None):
        if pickleFile is None:
            pickleFile = self.defaultPickleFile
        # Remove MAP dll (problematic in pickle file)
        if self.WT.MAP is not None:
            self.WT.MAP.lib=None
            self.WT.MAP = None
        d = {'fstFilename':self.fstFilename, 'WT':self.WT}
        LinearStateSpace.save(self, pickleFile, d)
        print('FASTLinModel: writing PKL: ', pickleFile)

    def load(self, pickleFile=None):
        if pickleFile is None:
            pickleFile = self.defaultPickleFile
        print('FASTLinModel: loading PKL:',pickleFile)

        d = LinearStateSpace.load(self, pickleFile)
        self.WT          = d['WT']
        self.fstFilename = d['fstFilename']



# --------------------------------------------------------------------------------}
# --- Class to handle a FTNSB model from OpenFAST
# --------------------------------------------------------------------------------{
class FASTLinModelFTNSB(FASTLinModel):

    def __init__(self, fstFilename=None, linFiles=None, pickleFile=None, usePickle=False):
        """ 
        inputFile: a lin file or a fst file
        """
        FASTLinModel.__init__(self, fstFilename, linFiles, pickleFile, usePickle=usePickle)





# --------------------------------------------------------------------------------}
# --- Creating a TNSB model from a FAST model. Used to be called FASTLinModel
# --------------------------------------------------------------------------------{
class FASTLinModelTNSB():
    def __init__(self, ED_or_FST_file, StateFile=None, nShapes_twr=1, nShapes_bld=0, DEBUG=False):

        # --- Input data from fst and ED file
        ext=os.path.splitext(ED_or_FST_file)[1]
        if ext.lower()=='.fst':
            FST=weio.read(ED_or_FST_file)
            rootdir = os.path.dirname(ED_or_FST_file)
            EDfile = os.path.join(rootdir,FST['EDFile'].strip('"')).replace('\\','/')
        else:
            EDfile=ED_or_FST_file
        self.ED= weio.read(EDfile)

        # --- Loading linear model
        if StateFile is not None:
            self.A,self.B,self.C,self.D,self.M = loadLinStateMatModel(StateFile)
        else:
            raise NotImplementedError()
        self.sX = self.A.columns

        self.nGear = self.ED['GBRatio']
        self.theta_tilt=-self.ED['ShftTilt']*np.pi/180 # NOTE: tilt has wrong orientation in FAST
        # --- Initial conditions
        omega_init = self.ED['RotSpeed']*2*np.pi/60 # rad/s
        psi_init   = self.ED['Azimuth']*np.pi/180 # rad
        FA_init    = self.ED['TTDspFA']
        iPsi     = list(self.sX).index('psi_rot_[rad]')
        nDOFMech = int(len(self.A)/2)
        q_init   = np.zeros(2*nDOFMech) # x2, state space

        if nShapes_twr>0:
            q_init[0] = FA_init

        q_init[iPsi]          = psi_init
        q_init[nDOFMech+iPsi] = omega_init

        self.q_init = q_init

    def __repr__(self):
        # TODO use printMat from welib.tools.strings
        def pretty_PrintMat(M,fmt='{:11.3e}',fmt_int='    {:4d}   ',sindent='   '):
            s=sindent
            for iline,line in enumerate(M):
                s+=''.join([(fmt.format(v) if int(v)!=v else fmt_int.format(int(v))) for v in line ])
                s+='\n'+sindent
            return s
        s=''
        s+='<FASTLinModel object>\n'
        s+='Attributes:\n'
        s+=' - A: State-State Matrix  \n'
        s+=pretty_PrintMat(self.A.values)+'\n'
        s+=' - B: State-Input Matrix  \n'
        s+=pretty_PrintMat(self.B.values)+'\n'
        s+=' - q_init: Initial conditions (state) \n'
        s+=str(self.q_init)+'\n'
        return s


def loadLinStateMatModel(StateFile, ScaleUnits=True, Adapt=True, ExtraZeros=False, nameMap={'SvDGenTq_[kNm]':'Qgen_[kNm]'}, ):
    """ 


    Load a pickle file contains A,B,C,D matrices either as sequence or dictionary.
    Specific treatments are possible:
       - ScaleUnits: convert to SI units deg->rad, rpm-> rad/s, kN->N
       - Adapt: 
       - Adapt: 
       - nameMap: rename columns and indices

    If a "model" is given specific treatments can be done

    NOTE:  the A, B, C, D matrices and state file were likely created by 
        FASTLin.average_subset()

    
    """
    import pickle
    # --- Subfunctions
    def load(filename):
        with open(filename,'rb') as f:
            dat=pickle.load(f)
        return dat

    # --- Load model
    dat = load(StateFile)
    if isinstance(dat,dict):
        A=dat['A']
        B=dat['B']
        C=dat['C']
        D=dat['D']
        M=None
        model =dat['model']
    else:
        model='TNSB'
        if len(dat)==4:
            M=None
            (A,B,C,D) = dat
        else:
            (A,B,C,D,M) = dat

    # --- Renaming
    for S,Mat in zip(['A','B','C','D'],[A,B,C,D]):
        for irow,row in enumerate(Mat.index.values):
            # Changing names
            if row=='SvDGenTq_[kNm]':
                Mat.index.values[irow]='Qgen_[kNm]'
                row='Qgen_[kNm]'



    # --- Scale units
    if ScaleUnits:
        # Changing rows
        for S,Mat in zip(['A','B','C','D'],[A,B,C,D]):
            Mat = matToSIunits(Mat, name=S, verbose=True)
    # --- ColMap
    if nameMap is not None:
        for S,Mat in zip(['A','B','C','D'],[A,B,C,D]):
            Mat.rename(nameMap, axis='columns', inplace=True)
            Mat.rename(nameMap, axis='index', inplace=True)

    # --- Numerics, 0
    for S,Mat in zip(['A','B','C','D'],[A,B,C,D]):
        Mat[np.abs(Mat)<1e-14]=0


    if model=='FNS' and A.shape[0]==6:
        pass
        #print(C)
        #print(D)
    elif model=='F1NS' and A.shape[0]==4:
        pass
    elif model=='F010000NS' and A.shape[0]==4:
        pass
    elif model=='F010010NS' and A.shape[0]==6:
        pass
    elif model=='F011010NS' and A.shape[0]==6:
        pass

    elif model=='FN' and A.shape[0]==4:
        pass

        
    elif model=='TNSB' and A.shape[0]==4:
        if Adapt==True:
            A.iloc[3,:]=0 # No state influence of ddpsi ! <<<< Important
            A.iloc[2,1]=0 # No psi influence of  ddqt
            A.iloc[2,3]=0 # No psi_dot influence of ddqt
            if ExtraZeros:
                B.iloc[0,:]=0 # No thrust influence on dqt
                B.iloc[1,:]=0 # No thrust influence on dpsi
            B.iloc[:,2]=0 # no pitch influence on states ! <<<< Important since value may only be valid around a given pitch
            if ExtraZeros:
                B.iloc[2,1]=0 # No Qgen influence on qtdot
                B.iloc[3,0]=0 # No thrust influence on psi
                D.iloc[0,1]=0  # No Qgen influence on IMU
            D.iloc[0,2]=0  # No pitch influences on IMU

            C.iloc[3,:]=0 # No states influence pitch
            C.iloc[2,3]=0 # No influence of psi on Qgen !<<< Important
    else:
        raise NotImplementedError('Model {} shape {}'.format(model,A.shape))

    # ---
    try:
        D['Qgen_[Nm]']['Qgen_[Nm]']=1
    except:
        pass

    return A,B,C,D,M
