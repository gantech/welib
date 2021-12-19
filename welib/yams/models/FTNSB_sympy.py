import numpy as np
from sympy import Matrix, symbols, simplify, Function, expand_trig, Symbol, diff
from sympy import cos,sin, transpose
from sympy import latex, python
from sympy.physics.mechanics import dynamicsymbols, ReferenceFrame, Point, inertia

#from welib.yams.sympy_tools import *
#from welib.yams.yams_sympy import DCMtoOmega
from welib.yams.yams_sympy       import YAMSRigidBody, YAMSInertialBody, YAMSFlexibleBody
from welib.yams.yams_sympy_model import YAMSModel
from welib.yams.models.FTNSB_sympy_symbols import *
from welib.tools.tictoc import Timer


_defaultOpts={
    'nB':3 , # Number of blades
    'floating':True,
    'yaw'    : 'fixed',  # 'fixed', 'dynamic' or 'zero'
    'tilt'   : 'fixed',  # 'fixed', 'dynamic' or 'zero'
    'Mform'  : 'TaylorExpanded', # 'symbolic',or 'TaylorExpanded'
    'mergeFndTwr':True, # Use one body for FND and TWR
    'tiltShaft':False, # Tilt shaft or nacelle
    'twrDOFDir':['x','y','x','y'], # Order in which the flexible DOF of the tower are set
    'collectiveBldDOF':False,      # Use the same degrees of freedom for all blades "collective"
    'linRot' : False,              #<<< Very important if True will assume that omegas are time derivatives of DOFs
    'rot_elastic_type':'Body',     #<<< Very important, SmallRot, or Body, will affect the rotation matrix
    'rot_elastic_subs':True,       #<<< Very important, will substitute alpha_y with nuy q. Recommended True
    'rot_elastic_smallAngle':False,#<<< Very important, will perform small angle approx: sin(nu q) = nu q and nu^2=0 !!! Will remove all nu^2 and nu^3 terms!! might not be recommended
    'fnd_loads':False, # Add loads on the foundation (restoring and buoyancy)
    'aero_torques':False, # Add aerodynamic torques
    'aero_forces':True, # Add aerodynamic torques
    'orderMM':2, #< order of taylor expansion for Mass Matrix
    'orderH':2,  #< order of taylor expansion for H term
    'verbose':False, 
}


def get_model(model_name, **opts):
    """ 

    model: string defining model

    opts: dictionary of options with keys:
        see _defaultOpts
    
    """

    for k,v in _defaultOpts.items():
        if k not in opts.keys():
            opts[k]=v
    for k,v in opts.items():
        if k not in _defaultOpts.keys():
            raise Exception('Key {} not supported for model options.'.format(k))
    #print(opts)
    verbose=opts['verbose']

    # --------------------------------------------------------------------------------}
    # --- Extract info from model name
    # --------------------------------------------------------------------------------{
    # Nicknames
    bFullRNA   = model_name.find('RNA')==-1
    bRotorOnly = model_name.find('R')==0

    if bRotorOnly and not bFullRNA:
        raise Exception('Cannot have "Rotor" and RNA')

    if bRotorOnly:
        # Rotor only, overriding options
        bFullRNA=True
        opts['nB']=int(model_name.split('R')[1][0]) 
        opts['mergeFndTwr'] = True
        opts['floating'] = False
        opts['yaw' ] = 'zero'
        opts['tilt'] = 'zero'

    # Default values, no DOF
    bFndDOFs = [False]*6
    bNac=False   # Is there Nacelle DOFs
    bSft=False   # Is there Shaft DOFs
    bBld=False   # Is there blade DOF
    nDOF_fnd   = 0 # Number of DOFs for foundation
    nDOF_twr   = 0 # Number of DOFs for tower
    nDOF_nac   = 0 # Number of DOFs for nacelle 
    nDOF_sft   = 0 # Number of DOFs for shaft
    nDOF_bld   = 0 # Total number of DOF per blade = nDOF_bld_e+nDOF_bld_f+nDOF_bld_t
    nDOF_bld_e = 0 # Number of edge DOF per blade
    nDOF_bld_f = 0 # Number of flap DOF per blade
    nDOF_bld_t = 0 # Number of torsion DOF per blade

    if not bRotorOnly:
        # "Foundation"/substructure
        sFnd= model_name.split('T')[0][1:] # TODO why not F????
        print('>>> sFND',sFnd, len(sFnd))
        if len(sFnd)==1:
            bFndDOFs   = [False]*6
            nDOF_fnd = int(sFnd[0])
            bFndDOFs[0]=nDOF_fnd>=1 # x
            bFndDOFs[4]=nDOF_fnd>=2 # phiy
            bFndDOFs[2]=nDOF_fnd==3 or nDOF_fnd==6 # z
            bFndDOFs[1]=nDOF_fnd>=5 # y
            bFndDOFs[3]=nDOF_fnd>=5 # phi_x
            bFndDOFs[5]=nDOF_fnd>=5 # phi_z
        else:
            bFndDOFs=[s=='1' for s in sFnd]

    if not bRotorOnly:
        # Tower
        nDOF_twr = int(model_name.split('T')[1][0])

    print('>>>bFullRNA',bFullRNA, bRotorOnly)
    if bFullRNA:
        # Rotor nacelle assembly is made of several bodies and DOFs
        bNac = model_name.find('N')>0
        bSft = model_name.find('S')>0
        bBld = model_name.find('B')>0
        if bNac:
            nDOF_nac = int(model_name.split('N')[1][0])
        if bSft:
            nDOF_sft = int(model_name.split('S')[1][0])
        if bBld:
            sDOF_bld = model_name.split('B')[1]
            if len(sDOF_bld)==1:
                nDOF_bld_f = int(sDOF_bld[0])
            elif len(sDOF_bld)==3:
                nDOF_bld_f = int(sDOF_bld[0])
                nDOF_bld_e = int(sDOF_bld[1])
                nDOF_bld_t = int(sDOF_bld[2])
            else:
                raise NotImplementedError()

    else:
        # Rotor nacelle assembly is one rigid body
        pass

    nDOF_fnd = sum(bFndDOFs)
    nDOF_bld = nDOF_bld_f+nDOF_bld_e+nDOF_bld_t

    bldDOFDir = []
    if True:
        bldDOFDir += ['x']*nDOF_bld_f
        bldDOFDir += ['y']*nDOF_bld_e
        bldDOFDir += ['t']*nDOF_bld_t
    else:
        pass # TODO distribute DOFs 1st flap, ed tors, 2nd flap, ed tors, ets


    if verbose:
        print('Degrees of freedom:')
        print('fnd',','.join(['1' if b else '0' for b in bFndDOFs]), 'twr',nDOF_twr, 'nac',nDOF_nac, 'sft',nDOF_sft, 'nB:{}'.format(opts['nB']), 'bld',nDOF_bld, '({},{},{}) {:s}'.format(nDOF_bld_f,nDOF_bld_e,nDOF_bld_t, ''.join(bldDOFDir)) )

    # --------------------------------------------------------------------------------}
    # --- Isolated bodies 
    # --------------------------------------------------------------------------------{
    # Reference frame
    ref = YAMSInertialBody('E') 

    twr       = None
    if not bRotorOnly:
        # Foundation, floater, always rigid for now
        if (not opts['floating']) or opts['mergeFndTwr']:
            fnd = None # the floater is merged with the twr, or we are not floating
        else:
            fnd = YAMSRigidBody('F', rho_G = [0,0,z_FG], J_diag=True) 
        # Tower
        if nDOF_twr==0:
            # Ridid tower
            twr = YAMSRigidBody('T', rho_G = [0,0,z_TG], J_diag=True) 
        elif nDOF_twr<=4:
            # Flexible tower
            twr = YAMSFlexibleBody('T', nDOF_twr, directions=opts['twrDOFDir'], orderMM=opts['orderMM'], orderH=opts['orderH'], predefined_kind='twr-z')

    # Nacelle rotor assembly
    blds = []
    rot  = None
    nac  = None
    if bFullRNA:
        if not bRotorOnly:
            # Nacelle
            nac = YAMSRigidBody('N', rho_G = [x_NG ,0, z_NG], J_cross=True) 

        # Shaft
        # TODO shaft mass and inertia...

        # Individual blades or rotor
        if bBld:
            if nDOF_bld==0:
                print('>>> Rigid blades')
                # NOTE: for now we assume the blades to be identical, hence the use of name_for_var
                for ib, b in enumerate(np.arange(opts['nB'])):
                    B = YAMSRigidBody('B{:d}'.format(ib+1), rho_G = [x_BG ,y_BG, z_BG], name_for_var='B')
                    blds.append(B)
            else:
                print('>>> Flexible blades')
                # NOTE: for now we assume the blades to be identical, hence the use of name_for_var

                if opts['collectiveBldDOF']:
                    for ib, b in enumerate(np.arange(opts['nB'])):
                        B = YAMSFlexibleBody('B{:d}'.format(ib+1), rho_G = [x_BG ,y_BG, z_BG], name_for_var='B', name_for_DOF='B') # <<< Collective DOF (same name)
                        blds.append(B)
                else:
                    for ib, b in enumerate(np.arange(opts['nB'])):
                        B = YAMSFlexibleBody('B{:d}'.format(ib+1), nDOF_bld, directions=bldDOFDir, orderMM=opts['orderMM'], orderH=opts['orderH'], predefined_kind='bld-z',
                                name_for_var='B')
                        blds.append(B)
        else:
            # Rotor
            rot = YAMSRigidBody('R', rho_G = [0,0,0], J_diag=True)
            rot.inertia = (inertia(rot.frame, Jxx_R, JO_R, JO_R), rot.origin)  # defining inertia at orign
    else:
        # Nacelle
        #nac = YAMSRigidBody('RNA', rho_G = [x_RNAG ,0, z_RNAG], J_diag=True) 
        nac = YAMSRigidBody('RNA', rho_G = [x_RNAG ,0, z_RNAG], J_cross=True) 
        rot = None

    # --------------------------------------------------------------------------------}
    # --- Body DOFs
    # --------------------------------------------------------------------------------{
    # --- Fnd
    if (not opts['floating']):
        fndDOFs   = []
        fndSpeeds = []
    else:
        fndDOFsAll    = [x, y, z, phi_x,     phi_y,       phi_z]
        fndSpeedsAll  = [xd,yd,zd,omega_x_T,omega_y_T,omega_z_T]
        fndDOFs    = [dof for active,dof in zip(bFndDOFs,fndDOFsAll)   if active]
        fndSpeeds  = [dof for active,dof in zip(bFndDOFs,fndSpeedsAll) if active]
    # --- Twr
    twrDOFs   = []
    twrSpeeds = []
    if nDOF_twr>0: # flexible tower
        twrDOFs   = twr.q
        twrSpeeds = twr.qd

    # --- Nac
    if nDOF_nac==2:
        opts['yaw']='dynamic'
        opts['tilt']='dynamic'
    if opts['tiltShaft'] and opts['tilt']=='dynamic':
        raise Exception('Cannot do tiltshaft with tilt dynamic')

    yawDOF  = {'zero':0, 'fixed':theta_yaw,  'dynamic':q_yaw }[opts['yaw']]
    tiltDOF = {'zero':0, 'fixed':theta_tilt, 'dynamic':q_tilt}[opts['tilt']]
    nacDOFs     = []
    nacSpeeds   = []
    nacKDEqSubs = []
    if opts['yaw']=='dynamic':
        nacDOFs     += [q_yaw]
        nacSpeeds   += [qd_yaw]
        nacKDEqSubs += [(qd_yaw, diff(q_yaw, time))]
    if opts['tilt']=='dynamic':
        nacDOFs     += [q_tilt]
        nacSpeeds   += [qd_tilt]
        nacKDEqSubs += [(qd_tilt, diff(q_tilt, time))]

    nacDOFsAct=(opts['yaw']=='dynamic',opts['tilt']=='dynamic')
    if nDOF_nac==0:
        if not (nacDOFsAct==(False,False)):
            raise Exception('If nDOF_nac is 0, yaw and tilt needs to be "fixed" or "zero"')
    elif nDOF_nac==1:
        if not (nacDOFsAct==(True,False) or nacDOFsAct==(False,True) ):
            raise Exception('If nDOF_nac is 1, yaw or tilt needs to be "dynamic"')
    else:
        if not (nacDOFsAct==(True,True)):
            raise Exception('If nDOF_nac is 2, yaw and tilt needs to be "dynamic"')

    # --- Shaft
    sftDOFs  =[]
    sftSpeeds=[]
    if bFullRNA:
        if nDOF_sft==1:
            sftDOFs   = [psi]
            sftSpeeds = [omega_x_R]
        elif nDOF_sft==0:
            pass
        else:
            raise Exception('nDOF shaft should be 0 or 1')

    # --- Blade/Rotor
    bldDOFs=[] 
    bldSpeeds=[] 
    if bFullRNA:
        # --- Twr
        bldDOFs   = []
        bldSpeeds = []
        if nDOF_bld>0: # flexible tower
            for ib, bld in enumerate(blds): 
                bldDOFs   += bld.q
                bldSpeeds += bld.qd

    coordinates = fndDOFs   + twrDOFs   + nacDOFs   + sftDOFs   + bldDOFs 
    speeds      = fndSpeeds + twrSpeeds + nacSpeeds + sftSpeeds + bldSpeeds  # Order determine eq order

    if verbose:
        print('Coordinates:',coordinates)
        print('speeds     :',speeds)



    # --------------------------------------------------------------------------------}
    # --- Connections between bodies
    # --------------------------------------------------------------------------------{
    z_OT = Symbol('z_OT')
    if opts['floating']:
        rel_pos=[0,0,0]
        rel_pos[0] = x      if bFndDOFs[0] else 0
        rel_pos[1] = y      if bFndDOFs[1] else 0
        rel_pos[2] = z+z_OT if bFndDOFs[2] else z_OT
        rots =[0,0,0]
        rots[0] = phi_x if bFndDOFs[3] else 0
        rots[1] = phi_y if bFndDOFs[4] else 0
        rots[2] = phi_z if bFndDOFs[5] else 0
        if nDOF_fnd==0:
            #print('Rigid connection ref twr', rel_pos)
            ref.connectTo(twr, type='Rigid' , rel_pos=rel_pos)
        elif nDOF_fnd==1: 
            #print('Constraint connection ref twr')
            #ref.connectTo(twr, type='Free' , rel_pos=(x,0,z_OT), rot_amounts=(0    , x * symbols('nu'), 0   ), rot_order='XYZ')
            print('>>>> TODO TODO TODO FTNSB_sympy, commented hacked case for nDOF_fnd==1')
            ref.connectTo(twr, type='Free' , rel_pos=rel_pos, rot_amounts=rots, rot_order='XYZ')  #NOTE: rot order is not "optimal".. phi_x should be last
        else:
            #print('Free connection ref twr', rel_pos, rots)
            ref.connectTo(twr, type='Free' , rel_pos=rel_pos, rot_amounts=rots, rot_order='XYZ')  #NOTE: rot order is not "optimal".. phi_x should be last
            #ref.connectTo(twr, type='Free' , rel_pos=rel_pos, rot_amounts=(rots[2],rots[1],rots[0]), rot_order='ZYX')  #NOTE: rot order is not "optimal".. phi_x should be last
    else:
        #print('Rigid connection ref twr')
        ref.connectTo(twr, type='Rigid' , rel_pos=(0,0,0))

    # Rigid connection between twr and fnd if fnd exists
    if fnd is not None:
        #print('Rigid connection twr fnd')
        if nDOF_twr==0:
            twr.connectTo(fnd, type='Rigid', rel_pos=(0,0,0)) # -L_F
        else:
            twr.connectTo(fnd, type='Rigid', rel_pos=(0,0,0)) # -L_F

    if nDOF_twr==0:
        # Tower rigid -> Rigid connection to nacelle
        # TODO TODO L_T or twr.L
        #if nDOF_nac==0:
        #print('Rigid connection twr nac')
        #else:
        #print('Dynamic connection twr nac')

        if opts['tiltShaft']:
            # Shaft will be tilted, not nacelle
            twr.connectTo(nac, type='Rigid', rel_pos=(0,0,L_T)  , rot_amounts=(yawDOF,0,0), rot_order='ZYX')
        else:
            # Nacelle is tilted
            twr.connectTo(nac, type='Rigid', rel_pos=(0,0,L_T)  , rot_amounts=(yawDOF,tiltDOF,0), rot_order='ZYX')

    else:
        # Flexible tower -> Flexible connection to nacelle
        #print('Flexible connection twr nac')
        if opts['tiltShaft']:
            twr.connectToTip(nac, type='Joint', rel_pos=(0,0,twr.L)  , rot_amounts=(yawDOF, 0      , 0), rot_order='ZYX', rot_type_elastic=opts['rot_elastic_type'], doSubs=opts['rot_elastic_subs'])
        else:
            twr.connectToTip(nac, type='Joint', rel_pos=(0,0,twr.L)  , rot_amounts=(yawDOF, tiltDOF, 0), rot_order='ZYX', rot_type_elastic=opts['rot_elastic_type'], doSubs=opts['rot_elastic_subs'])

    if bFullRNA:
        if bBld:
            raise NotImplementedError()
        else:
            if opts['tiltShaft']:
                if nDOF_sft==0:
                    nac.connectTo(rot, type='Joint', rel_pos=(x_NR,0,z_NR), rot_amounts=(0,tiltDOF,0), rot_order='ZYX')
                else:
                    nac.connectTo(rot, type='Joint', rel_pos=(x_NR,0,z_NR), rot_amounts=(0,tiltDOF,psi), rot_order='ZYX')
            else:
                if nDOF_sft==0:
                    nac.connectTo(rot, type='Joint', rel_pos=(x_NR,0,z_NR), rot_amounts=(0,0      ,0), rot_order='ZYX')
                else:
                    nac.connectTo(rot, type='Joint', rel_pos=(x_NR,0,z_NR), rot_amounts=(0,0      ,psi), rot_order='ZYX')


    # --- Defining Body rotational velocities
    omega_TE = twr.ang_vel_in(ref)        # Angular velocity of nacelle in inertial frame
    omega_NT = nac.ang_vel_in(twr.frame)  # Angular velocity of nacelle in inertial frame
    if rot is not None:
        omega_RN = rot.ang_vel_in(nac.frame)  # Angular velocity of rotor wrt Nacelle (omega_R-omega_N)

    # --- Kinetics
    body_loads       = []
    bodies           = []
    g                = symbols('g')
    g_vect           = -g * ref.frame.z
    # Foundation/floater loads
    if fnd is not None:
        bodies+= [fnd]
        grav_F = (fnd.masscenter, -fnd.mass * g * ref.frame.z)
        # Point of application for Buoyancy and mooring
        P_B = twr.origin.locatenew('P_B', z_TB * fnd.frame.z) # <<<< Measured from T
        P_M = twr.origin.locatenew('P_M', z_TM * fnd.frame.z) # <<<< Measured from T
        P_B.v2pt_theory(twr.origin, ref.frame, twr.frame); # PB & T are fixed in e_T
        P_M.v2pt_theory(twr.origin, ref.frame, twr.frame); # PM & T are fixed in e_T
        if opts['fnd_loads']:
            K_Mx, K_My, K_Mz          = symbols('K_x_M, K_y_M, K_z_M') # Mooring restoring
            K_Mphix, K_Mphiy, K_Mphiz = symbols('K_phi_x_M, K_phi_y_M, K_phi_z_M') # Mooring restoring
            F_B = dynamicsymbols('F_B') # Buoyancy force
            #print('>>> Adding fnd loads. NOTE: reference might need to be adapted')
            # Buoyancy
            body_loads  += [(fnd, (P_B, F_B * ref.frame.z))]
            ## Restoring mooring and torques
            fr=0
            fr += -K_Mx * x *ref.frame.x if bFndDOFs[0] else 0
            fr += -K_My * y *ref.frame.y if bFndDOFs[1] else 0
            fr += -K_Mz * z *ref.frame.z if bFndDOFs[2] else 0
            Mr += -K_MPhix * phi_x *ref.frame.x if bFndDOFs[3] else 0
            Mr += -K_MPhiy * phi_y *ref.frame.y if bFndDOFs[4] else 0
            Mr += -K_MPhiz * phi_z *ref.frame.z if bFndDOFs[5] else 0
            body_loads  += [(fnd, (P_M,  fr))]
            body_loads  += [(fnd, (fnd.frame, Mr))]
        body_loads  += [(fnd,grav_F)]

    # Tower loads
    grav_T       = (twr.masscenter, -twr.mass * g * ref.frame.z)
    bodies      += [twr]
    body_loads  += [(twr,grav_T)]  

    # Nacelle loads
    grav_N = (nac.masscenter, -nac.mass * g * ref.frame.z)
    bodies      += [nac]
    body_loads  += [(nac,grav_N)]  

    T_a              = dynamicsymbols('T_a') # NOTE NOTE
    #T_a              = Function('T_a')(dynamicsymbols._t, *coordinates, *speeds) # NOTE: to introduce it in the linearization, add coordinates
    M_ax, M_ay, M_az = dynamicsymbols('M_x_a, M_y_a, M_z_a') # Aero torques
    if bFullRNA:
        if bBld:
            raise NotImplementedError()
        else:
            # Rotor loads
            grav_R = (rot.masscenter, -M_R * g * ref.frame.z)
            bodies      += [rot]
            body_loads  += [(rot,grav_R)]  

            # NOTE: loads on rot, but expressed in N frame
            if opts['tiltShaft']:
                # TODO actually tilt shaft, introduce non rotating shaft body
                if opts['aero_forces']:
                    #thrustR = (rot.origin, T_a *cos(tiltDOF) * nac.frame.x -T_a *sin(tiltDOF) * nac.frame.z)
                    thrustR = (rot.origin, T_a * rot.frame.x)
                if opts['aero_torques']:
                    print('>>> Adding aero torques 1')
                    M_a_R = (rot.frame, M_ax*rot.frame.x )# TODO TODO
                    body_loads+=[(rot, M_a_R)]
            else:
                thrustR = (rot.origin, T_a * nac.frame.x )
                #thrustR = (rot.origin, T_a * rot.frame.x )
                #M_a_R = (rot.frame, M_ax*rot.frame.x +  M_ay*rot.frame.y  + M_az*rot.frame.z) # TODO TODO TODO introduce a non rotating shaft
                if opts['aero_torques']:
                    print('>>> Adding aero torques 2')
                    #M_a_R = (nac.frame, M_ax*nac.frame.x +  M_ay*nac.frame.y  + M_az*nac.frame.z) 
                    M_a_R = (rot.frame, M_ax*rot.frame.x +  M_ay*rot.frame.y  + M_az*rot.frame.z)
                    body_loads+=[(nac, M_a_R)]
            body_loads  += [(rot,thrustR)]

    else:
        # RNA loads, point load at R
        R=Point('R')
        R.set_pos(nac.origin, x_NR * nac.frame.x + z_NR* nac.frame.z)
        R.set_vel(nac.frame, 0 * nac.frame.x)
        R.v2pt_theory(nac.origin, ref.frame, nac.frame)
        #thrustN = (nac.masscenter, T * nac.frame.x)
        if opts['tiltShaft']:
            thrustN = (R, T_a *cos(tiltDOF) * nac.frame.x -T_a *sin(tiltDOF) * nac.frame.z)
        else:
            thrustN = (R, T_a * nac.frame.x )
        if opts['aero_forces']:
            body_loads  += [(nac,thrustN)]

        if opts['aero_torques']:
            print('>>> Adding aero torques 3')
            if opts['tiltShaft']:
                # NOTE: for a rigid RNA we keep only M_y and M_z, no shaft torque
                x_tilted = cos(tiltDOF) * nac.frame.x - sin(tiltDOF) * nac.frame.z
                z_tilted = cos(tiltDOF) * nac.frame.y + sin(tiltDOF) * nac.frame.x
                M_a_N = (nac.frame,                  M_ay*nac.frame.y + M_az*z_tilted) 
            else:
                M_a_N = (nac.frame, M_ax*nac.frame.x +  M_ay*nac.frame.y  + M_az*nac.frame.z)
            body_loads  += [(nac, M_a_N)]  
    if verbose:
        print('Loads:')
        for (b,l) in body_loads:
            print(b.name, l)




    # --------------------------------------------------------------------------------}
    # --- Kinematic equations 
    # --------------------------------------------------------------------------------{
    kdeqsSubs =[]
    # --- Fnd
    if not opts['floating']:
        pass
    else:
        # Kdeqs for fnd: 
        #  : (xd, diff(x,time)) and  (omega_y_T, diff(phi_y,time))
        fndVelAll = [diff(x,time), diff(y,time),  diff(z,time)]
        if opts['linRot']:
            fndVelAll += [diff(phi_x,time), diff(phi_y,time),  diff(phi_z,time)]  
        else:
            #print('>>>>>>>> TODO sort out which frame')
            #fndVelAll +=[ omega_TE.dot(ref.frame.x).simplify(), omega_TE.dot(ref.frame.y).simplify(), omega_TE.dot(ref.frame.z).simplify()]  
            fndVelAll +=[ omega_TE.dot(twr.frame.x).simplify(), omega_TE.dot(twr.frame.y).simplify(), omega_TE.dot(twr.frame.z).simplify()]  
        kdeqsSubs+=[ (fndSpeedsAll[i], fndVelAll[i]) for i,dof in enumerate(bFndDOFs) if dof] 

    # --- Twr
    if nDOF_twr==0:
        pass
    else:
        kdeqsSubs +=[ (twr.qd[i], twr.qdot[i]) for i,_ in enumerate(twr.q)]; 

    # --- Nac
    kdeqsSubs+=nacKDEqSubs

    # --- Shaft
    if bFullRNA:
        if bBld:
            raise NotImplementedError()
        else:
            if nDOF_sft==1:
                #print('>>>>>>>> TODO sort out which frame')
                # I believe we should use omega_RE
                kdeqsSubs+=[ (omega_x_R, omega_RN.dot(rot.frame.x).simplify()) ]  

    # --- Create a YAMS wrapper model
    model = YAMSModel(name=model_name)
    model.opts        = opts
    model.ref         = ref
    model.bodies      = bodies
    model.body_loads  = body_loads
    model.coordinates = coordinates
    model.speeds      = speeds
    model.kdeqsSubs   = kdeqsSubs
    #print(model)

    model.fnd=fnd
    model.twr=twr
    model.nac=nac
    model.rot=rot
    #model.sft=sft
    #model.bld=bld
    model.g_vect=g_vect

    # Small angles
    model.smallAnglesFnd    = [phi_x,phi_y,phi_z]
    if nDOF_twr>0:
        if opts['rot_elastic_smallAngle']:
            model.smallAnglesTwr    = twr.vcList
        else:
            model.smallAnglesTwr    = []
    else:
        model.smallAnglesTwr    = []

    model.smallAnglesNac = []
    if opts['yaw']=='dynamic':
        model.smallAnglesNac += [q_yaw]
    if opts['tilt']=='dynamic':
        model.smallAnglesNac += [q_tilt]
    model.smallAngles=model.smallAnglesFnd + model.smallAnglesTwr + model.smallAnglesNac

    # Shape normalization
    if nDOF_twr>0:
        model.shapeNormSubs= [(v,1) for v in twr.ucList]
    else:
        model.shapeNormSubs= []

    return model
