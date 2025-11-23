import time
import keyboard
import random
import win32api
import win32con 
import sys
import os

# ================= CONFIGURATION =================
KEYS = {
    'storm_arrow': '1',       # Main Spammer
    'torrent_volley': '2',    # Torrent Volley / Enhance Torrent
    'arrow_rain': '3',        # Rain Arrow (Energy/Stack building)
    'wildcall': '4',          # Buff + Stomp
    'focus': '5',             # Buff
    'ultimate': 'r',          # Ultimate
    'imagine_1': 'z',
    'imagine_2': 'x',
    'attack': 'left',         # Normal Attack during ALL gaps
}

# WINDOWS VIRTUAL KEY CODES
VK_CODES = {
    '1': 0x31, '2': 0x32, '3': 0x33, '4': 0x34, '5': 0x35, 
    'r': 0x52, 'z': 0x5A, 'x': 0x58,
}
VK_MOUSE_DOWN = win32con.MOUSEEVENTF_LEFTDOWN
VK_MOUSE_UP = win32con.MOUSEEVENTF_LEFTUP

# CONTROLS
START_STOP_KEY = 'f8'
EXIT_KEY = 'f9'

# ================= STARTUP REQUIREMENTS =================
STARTUP_REQUIREMENTS = {
    'photon_energy': 120,      # MUST start with full energy
    'torrent_stacks': 30,      # MUST start with 30 torrent stacks  
    'all_cooldowns_ready': True # All skills should be off cooldown
}

# OPTIMIZED TIMERS - Tighter for maximum DPS
TIMER = {
    'MAX_BURN': 3.8,         # Slightly reduced for better pacing
    '80_PHOTON': 1.2,        # Tighter timing
    '40_PHOTON': 2.4,        # Reduced gaps
    '60_70_PHOTON': 1.8,     # Faster transitions
    'FILL_PHOTON': 1.3,      # Faster filling
    'STALL_CD': 2.3,         # Reduced stall time
    'GCD': 0.15,             # Faster global cooldown
}

# COOLDOWNS (in seconds) - UPDATED WITH CORRECT VALUES
LONG_COOLDOWNS = {
    'ultimate': 60,
    'wildcall': 45,
    'focus': 45,
    'imagine_1': 120,        # UPDATED: Z ability cooldown to 120 seconds
    'imagine_2': 100,        # UPDATED: X ability cooldown to 100 seconds
}

# ================= INPUT TIMING SETTINGS =================
# Increased delays to ensure game registers all inputs
INPUT_TIMING = {
    'min_hold': 0.05,        # Increased minimum key hold time
    'max_hold': 0.08,        # Increased maximum key hold time  
    'min_delay': 0.05,       # Increased minimum delay between actions
    'max_delay': 0.10,       # Increased maximum delay between actions
    'off_cooldown_delay': 0.4,  # Delay between off-cooldown skills
    'check_interval': 1.0,   # Check for off-cooldown skills every second
}

# ================= STATE MACHINE =================
paused = True
current_state = 'START'
state_start_time = 0
cycle_count = 0
last_unpause_time = 0
script_start_time = time.time()

# Cooldown tracking - use negative values to indicate ready immediately
last_cast = {
    'ultimate': -999,        # Negative = ready immediately
    'wildcall': -999,
    'focus': -999,
    'torrent_volley': -999,
    'arrow_rain': -999,
    'imagine_1': -999,       # Z ready immediately
    'imagine_2': -999,       # X ready immediately
}

# Auto-attack cooldown tracking
last_auto_attack = 0
AUTO_ATTACK_COOLDOWN = 0.3  # Auto-attack every 300ms

# Track last off-cooldown usage to prevent spam
last_off_cooldown_check = 0

# ================= ROTATION SEQUENCES =================

# OPENER: 13 -> 19 -> 30 -> 6 stacks
OPENER_SEQUENCE = [
    ('OPENER_BUFFS', 0),                    
    ('OPENER_SPAM_TO_0', TIMER['MAX_BURN']), 
    ('OPENER_ENHANCE_TORRENT', TIMER['GCD']), 
    ('OPENER_SPAM_TO_80', TIMER['80_PHOTON']), 
    ('OPENER_RAIN', TIMER['GCD']),           
    ('OPENER_SPAM_TO_40', TIMER['40_PHOTON']), 
    ('OPENER_TORRENT_PRE_WILD', TIMER['GCD']), 
    ('OPENER_WILDCALL_STOMP', TIMER['GCD']), 
    ('OPENER_SPAM_TO_0_13STACK', TIMER['MAX_BURN']), 
    ('OPENER_FILL_19STACK', TIMER['FILL_PHOTON']), 
    ('OPENER_FOCUS', TIMER['GCD']),          
    ('OPENER_SPAM_TO_60_70', TIMER['60_70_PHOTON']), 
    ('OPENER_TORRENT_30STACK', TIMER['GCD']), 
    ('OPENER_ENHANCE_SPAM_6STACK', TIMER['MAX_BURN']), 
]

# CYCLE: 6 -> 17 stacks
CYCLE_6_17_SEQUENCE = [
    ('CYCLE_FILL_1_3', TIMER['FILL_PHOTON']), 
    ('CYCLE_SPAM_TO_40', TIMER['40_PHOTON']), 
    ('CYCLE_TORRENT_PRE_WILD', TIMER['GCD']), 
    ('CYCLE_WILDCALL_STOMP', TIMER['GCD']),  
    ('CYCLE_SPAM_TO_0_17STACK', TIMER['MAX_BURN']), 
]

# CYCLE: Stall -> 6 stacks
CYCLE_STALL_SEQUENCE = [
    ('CYCLE_STALL_FILL_MAX', TIMER['FILL_PHOTON']), 
    ('CYCLE_STALL_NORMAL', TIMER['STALL_CD']), 
    ('CYCLE_STALL_BUFFS', TIMER['GCD']),      
    ('CYCLE_ENGAGE_PHOTON', TIMER['GCD']),    
    ('CYCLE_SPAM_TO_60_70', TIMER['60_70_PHOTON']), 
    ('CYCLE_RAIN_TORRENT', TIMER['GCD'] * 2), 
    ('CYCLE_WILDCALL_STOMP', TIMER['GCD']),   
    ('CYCLE_SPAM_TO_0', TIMER['MAX_BURN']),   
    ('CYCLE_ENHANCE_SPAM_6STACK', TIMER['MAX_BURN']), 
]

def is_admin():
    """Check if running with admin privileges"""
    try:
        import ctypes
        return ctypes.windll.shell32.IsUserAnAdmin()
    except:
        return False

def game_safe_delay(min_delay=0.05, max_delay=0.10):
    """Create delays that ensure the game can register inputs"""
    delay_time = random.uniform(min_delay, max_delay)
    time.sleep(delay_time)

def game_safe_hold():
    """Generate key hold duration that ensures game registration"""
    hold_time = random.uniform(INPUT_TIMING['min_hold'], INPUT_TIMING['max_hold'])
    return hold_time

def press(key, hold=None, extra_delay=0.1):
    """
    Game-safe key press with guaranteed input registration
    """
    if key is None: 
        return
    
    if hold is None:
        hold = game_safe_hold()
    
    try:
        if key == 'left':
            win32api.mouse_event(VK_MOUSE_DOWN, 0, 0, 0, 0)
            time.sleep(hold)
            win32api.mouse_event(VK_MOUSE_UP, 0, 0, 0, 0)
        elif key in VK_CODES:
            vk_code = VK_CODES[key]
            # Key down
            win32api.keybd_event(vk_code, 0, 0, 0)
            time.sleep(hold)  # Hold the key down
            # Key up
            win32api.keybd_event(vk_code, 0, win32con.KEYEVENTF_KEYUP, 0)
    except Exception as e:
        print(f"Input error for '{key}': {e}")
    
    # Extra delay to ensure game registers the input completely
    time.sleep(extra_delay)

def auto_attack():
    """Execute auto-attack if cooldown is ready"""
    global last_auto_attack
    current_time = time.time()
    if current_time - last_auto_attack >= AUTO_ATTACK_COOLDOWN:
        press(KEYS['attack'], extra_delay=0.05)  # Shorter delay for auto-attacks
        last_auto_attack = current_time

def cast_wildcall_stomp():
    """Executes Wildcall -> Wait -> Wildcall (Stomp) with game-safe timing"""
    press(KEYS['wildcall'])
    # Wait for stomp timing with game-safe delay
    time.sleep(0.3)
    press(KEYS['wildcall'])

def advance_state(new_state, duration=0):
    """Move to next state"""
    global current_state, state_start_time
    current_state = new_state
    state_start_time = time.time()
    print(f"[Cycle {cycle_count}] -> {new_state} (Duration: {duration:.1f}s)")

def get_current_sequence():
    """Get current sequence based on state prefix"""
    if current_state.startswith('OPENER'):
        return OPENER_SEQUENCE
    elif current_state.startswith('CYCLE_6_17') or current_state.startswith('CYCLE_FILL') or current_state.startswith('CYCLE_SPAM') or current_state.startswith('CYCLE_TORRENT') or current_state.startswith('CYCLE_WILDCALL'):
        return CYCLE_6_17_SEQUENCE
    elif current_state.startswith('CYCLE_STALL') or current_state.startswith('CYCLE_ENGAGE') or current_state.startswith('CYCLE_RAIN'):
        return CYCLE_STALL_SEQUENCE
    return None

def find_next_state_index(sequence, current_state):
    """Find the index of the next state in sequence"""
    for i, (state, _) in enumerate(sequence):
        if state == current_state:
            return i + 1 if i + 1 < len(sequence) else -1
    return 0

def get_cooldown_remaining(skill_name):
    """Get remaining cooldown for a skill in seconds"""
    if skill_name not in last_cast or skill_name not in LONG_COOLDOWNS:
        return 0
    
    time_since_cast = time.time() - last_cast[skill_name]
    cooldown_duration = LONG_COOLDOWNS[skill_name]
    remaining = cooldown_duration - time_since_cast
    
    return max(remaining, 0)

def is_skill_ready(skill_name):
    """Check if a skill is off cooldown"""
    return get_cooldown_remaining(skill_name) <= 0

def update_cooldown(skill_name):
    """Update last cast time for a skill"""
    last_cast[skill_name] = time.time()

def print_cooldown_status():
    """Debug function to print current cooldown status"""
    status = []
    for skill in ['ultimate', 'wildcall', 'focus', 'imagine_1', 'imagine_2']:
        remaining = get_cooldown_remaining(skill)
        if remaining > 0:
            status.append(f"{skill}: {remaining:.1f}s")
        else:
            status.append(f"{skill}: READY")
    
    print(f"CDs: {', '.join(status)}")

def can_use_off_cooldown_skill_in_state(current_state):
    """
    Determine if an off-cooldown skill can be safely used in the current state
    Returns True for most states, False only for critical sequences
    """
    # States where we should NOT use off-cooldown skills (critical timing sequences)
    unsafe_states = [
        'TORRENT_PRE_WILD',  # Critical: Torrent must come before Wildcall
        'WILDCALL_STOMP',    # During wildcall stomp sequence
        'ENHANCE_TORRENT',   # During enhance torrent cast
        'RAIN_TORRENT',      # During rain+torrent sequence
    ]
    
    # Check if current state contains any unsafe pattern
    for unsafe in unsafe_states:
        if unsafe in current_state:
            return False
    
    # Safe to use off-cooldown skills in all other states
    return True

def execute_off_cooldown_skills():
    """Execute off-cooldown skills with guaranteed game registration"""
    global last_off_cooldown_check
    
    current_time = time.time()
    
    # Only check for off-cooldown skills every second to prevent spam
    if current_time - last_off_cooldown_check < INPUT_TIMING['check_interval']:
        return
        
    last_off_cooldown_check = current_time
    
    # Cooldown checks
    ult_ready = is_skill_ready('ultimate')
    imagine_1_ready = is_skill_ready('imagine_1')
    imagine_2_ready = is_skill_ready('imagine_2')
    
    # Only proceed if we can use skills in current state
    if not can_use_off_cooldown_skill_in_state(current_state):
        return
    
    skills_to_cast = []
    
    # Check which skills are ready
    if ult_ready:
        skills_to_cast.append(('ultimate', 'Ultimate'))
    if imagine_1_ready:
        skills_to_cast.append(('imagine_1', 'Z (Imagine 1)'))
    if imagine_2_ready:
        skills_to_cast.append(('imagine_2', 'X (Imagine 2)'))
    
    # If multiple skills are ready, cast them with guaranteed delays
    if skills_to_cast:
        print(f">>> [PRIORITY] Casting {len(skills_to_cast)} off-cooldown skill(s) <<<")
        
        for i, (skill_name, skill_display) in enumerate(skills_to_cast):
            print(f">>> Casting {skill_display} Immediately!")
            # Use longer extra delay for off-cooldown skills to ensure registration
            press(KEYS[skill_name], extra_delay=0.15)
            update_cooldown(skill_name)
            
            # Add guaranteed delay between multiple off-cooldown skills
            if i < len(skills_to_cast) - 1:  # Don't delay after the last skill
                time.sleep(INPUT_TIMING['off_cooldown_delay'])

def execute_rotation():
    global current_state, state_start_time, cycle_count, last_cast, last_unpause_time, last_auto_attack
    
    current_time = time.time()
    elapsed = current_time - state_start_time
    
    # Cooldown checks for rotation-specific skills
    wildcall_ready = is_skill_ready('wildcall')
    focus_ready = is_skill_ready('focus')
    
    # ========== OFF-COOLDOWN PRIORITY SYSTEM ==========
    # Use off-cooldown skills IMMEDIATELY when ready in ANY safe state
    execute_off_cooldown_skills()
    
    # ========== AUTO-ATTACK IN ALL GAPS ==========
    # Fill ALL downtime with auto-attacks, regardless of state
    auto_attack()
    
    # Get current sequence
    sequence = get_current_sequence()
    
    # Start state - begin opener
    if current_state == 'START':
        print(">>> Starting OPTIMIZED 13-19-30-6-17 Rotation <<<")
        print(">>> ALL OFF-COOLDOWN SKILLS will be used IMMEDIATELY when ready <<<")
        advance_state('OPENER_BUFFS', 0)
        return
    
    # Handle transition between sequences
    if not sequence:
        if current_state == 'TRANSITION_TO_CYCLE_6_17' or current_state.endswith('CYCLE_6_17'):
            print(">>> Transition to 6->17 Cycle")
            advance_state('CYCLE_FILL_1_3', TIMER['FILL_PHOTON'])
            return
        elif current_state == 'TRANSITION_TO_CYCLE_STALL' or current_state.endswith('CYCLE_STALL'):
            print(">>> Transition to Stall Cycle")
            advance_state('CYCLE_STALL_FILL_MAX', TIMER['FILL_PHOTON'])
            return
        else:
            print(f"ERROR: No sequence found for state: {current_state}")
            # Try to recover by going back to start
            advance_state('START', 0)
            return
    
    # If we just unpaused, restart the current cycle for safety
    if current_time - last_unpause_time < 1.0:
        if current_state.startswith('CYCLE_6_17'):
            print(">>> [UNPAUSE] Restarting 6->17 cycle from beginning")
            advance_state('CYCLE_FILL_1_3', TIMER['FILL_PHOTON'])
            return
        elif current_state.startswith('CYCLE_STALL'):
            print(">>> [UNPAUSE] Restarting stall cycle from beginning")
            advance_state('CYCLE_STALL_FILL_MAX', TIMER['FILL_PHOTON'])
            return
    
    # Find current state duration
    current_duration = 0
    current_index = -1
    for i, (state, duration) in enumerate(sequence):
        if state == current_state:
            current_duration = duration
            current_index = i
            break
    
    if current_index == -1:
        print(f"ERROR: State {current_state} not found in sequence")
        advance_state('START', 0)
        return
    
    # ========== STATE EXECUTION ==========
    
    # OPENER STATES
    if current_state == 'OPENER_BUFFS':
        print(">>> Casting buffs: Focus, Wildcall")
        # Note: Z and X are now handled by off-cooldown system above
        press(KEYS['focus'])
        update_cooldown('focus')
        press(KEYS['wildcall'])
        update_cooldown('wildcall')
        advance_state('OPENER_SPAM_TO_0', TIMER['MAX_BURN'])
        
    elif current_state == 'OPENER_ENHANCE_TORRENT':
        print(">>> Casting Enhance Torrent")
        press(KEYS['torrent_volley'])
        update_cooldown('torrent_volley')
        advance_state('OPENER_SPAM_TO_80', TIMER['80_PHOTON'])
        
    elif current_state == 'OPENER_RAIN':
        print(">>> Casting Rain Arrow")
        press(KEYS['arrow_rain'])
        update_cooldown('arrow_rain')  # FIXED: Removed extra bracket
        advance_state('OPENER_SPAM_TO_40', TIMER['40_PHOTON'])
        
    elif current_state == 'OPENER_TORRENT_PRE_WILD':
        print(">>> CRITICAL: Torrent BEFORE Wildcall")
        press(KEYS['torrent_volley'])
        update_cooldown('torrent_volley')
        advance_state('OPENER_WILDCALL_STOMP', TIMER['GCD'])
        
    elif current_state == 'OPENER_WILDCALL_STOMP':
        print(">>> Wildcall Stomp")
        cast_wildcall_stomp()
        update_cooldown('wildcall')
        advance_state('OPENER_SPAM_TO_0_13STACK', TIMER['MAX_BURN'])
        
    elif current_state == 'OPENER_FOCUS':
        print(">>> Casting Focus")
        press(KEYS['focus'])
        update_cooldown('focus')
        advance_state('OPENER_SPAM_TO_60_70', TIMER['60_70_PHOTON'])
        
    elif current_state == 'OPENER_TORRENT_30STACK':
        print(">>> 30 Stack Torrent (NO RAIN)")
        press(KEYS['torrent_volley'])
        update_cooldown('torrent_volley')
        advance_state('OPENER_ENHANCE_SPAM_6STACK', TIMER['MAX_BURN'])
        
    # CYCLE 6->17 STATES
    elif current_state == 'CYCLE_TORRENT_PRE_WILD':
        print(">>> CRITICAL: Torrent BEFORE Wildcall")
        press(KEYS['torrent_volley'])
        update_cooldown('torrent_volley')
        advance_state('CYCLE_WILDCALL_STOMP', TIMER['GCD'])
        
    elif current_state == 'CYCLE_WILDCALL_STOMP':
        print(">>> Wildcall Stomp")
        cast_wildcall_stomp()
        update_cooldown('wildcall')
        advance_state('CYCLE_SPAM_TO_0_17STACK', TIMER['MAX_BURN'])
        
    # STALL CYCLE STATES  
    elif current_state == 'CYCLE_STALL_NORMAL':
        # Spam normal attack (already handled by global auto-attack)
        # Check if we should advance (duration-based state)
        if elapsed >= current_duration:
            advance_state('CYCLE_STALL_BUFFS', TIMER['GCD'])
            
    elif current_state == 'CYCLE_STALL_BUFFS':
        print(">>> Stall Buffs: Focus")
        # Note: Z and X are now handled by off-cooldown system above
        if focus_ready:
            press(KEYS['focus'])
            update_cooldown('focus')
        advance_state('CYCLE_ENGAGE_PHOTON', TIMER['GCD'])
        
    elif current_state == 'CYCLE_ENGAGE_PHOTON':
        print(">>> Engaging Photon Mode")
        press(KEYS['storm_arrow'])
        advance_state('CYCLE_SPAM_TO_60_70', TIMER['60_70_PHOTON'])
        
    elif current_state == 'CYCLE_RAIN_TORRENT':
        print(">>> Rain + Torrent")
        press(KEYS['arrow_rain'])
        update_cooldown('arrow_rain')
        press(KEYS['torrent_volley'])
        update_cooldown('torrent_volley')
        advance_state('CYCLE_WILDCALL_STOMP', TIMER['GCD'])
        
    # SPAM STATES (execute during duration)
    elif current_duration > 0 and elapsed < current_duration:
        if 'FILL' in current_state:
            # Spam 1+3 to fill photon
            press(KEYS['storm_arrow'], extra_delay=0.05)  # Shorter delay for spam
            press(KEYS['arrow_rain'], extra_delay=0.05)
        elif 'SPAM' in current_state:
            # Spam storm arrow (auto-attack already handled globally)
            press(KEYS['storm_arrow'], extra_delay=0.05)
                
        # Global: Use Wildcall if ready during any spam phase
        if wildcall_ready and 'WILDCALL' not in current_state:
            print(">> [CD] Wildcall Stomp")
            cast_wildcall_stomp()
            update_cooldown('wildcall')
    
    # Advance to next state when duration elapsed (for duration-based states)
    elif current_duration > 0 and elapsed >= current_duration:
        next_state_index = current_index + 1
        if next_state_index < len(sequence):
            next_state, next_duration = sequence[next_state_index]
            advance_state(next_state, next_duration)
        else:
            # End of sequence, transition to next phase
            if sequence == OPENER_SEQUENCE:
                cycle_count += 1
                print(">>> Opener complete, transitioning to 6->17 cycle")
                print_cooldown_status()
                advance_state('CYCLE_FILL_1_3', TIMER['FILL_PHOTON'])
            elif sequence == CYCLE_6_17_SEQUENCE:
                cycle_count += 1
                print(">>> 6->17 cycle complete, transitioning to stall cycle")
                print_cooldown_status()
                advance_state('CYCLE_STALL_FILL_MAX', TIMER['FILL_PHOTON'])
            elif sequence == CYCLE_STALL_SEQUENCE:
                cycle_count += 1
                print(">>> Stall cycle complete, transitioning to 6->17 cycle")
                print_cooldown_status()
                advance_state('CYCLE_FILL_1_3', TIMER['FILL_PHOTON'])

def main():
    global paused, current_state, state_start_time, cycle_count, last_cast, last_unpause_time, script_start_time, last_auto_attack, last_off_cooldown_check
    
    if not is_admin():
        print("WARNING: Run as Administrator for inputs to work!")
        time.sleep(2)
    
    print("=== GAME-SAFE BLAST ARCHER ROTATION ===")
    print(f"Start: {START_STOP_KEY} | Exit: {EXIT_KEY}")
    print("=======================================")
    print("🔥 CRITICAL STARTUP REQUIREMENTS:")
    print(f"• Photon Energy: {STARTUP_REQUIREMENTS['photon_energy']}/120")
    print(f"• Torrent Stacks: {STARTUP_REQUIREMENTS['torrent_stacks']}")
    print(f"• All Cooldowns: READY")
    print("=======================================")
    print("GAME-SAFE INPUT SYSTEM:")
    print("- Guaranteed input registration")
    print("- Proper delays between all key presses")
    print("- Ultimate, Z, X used immediately when ready")
    print("- 400ms delays between off-cooldown skills")
    print("- Auto-attack fills ALL gaps")
    
    last_key_check = 0
    
    while True:
        current_time = time.time()
        
        # Check controls
        if current_time - last_key_check > 0.1:
            if keyboard.is_pressed(EXIT_KEY):
                print("Exit pressed")
                break
                
            if keyboard.is_pressed(START_STOP_KEY):
                paused = not paused
                if not paused:
                    print(">>> STARTING GAME-SAFE ROTATION <<<")
                    print(">>> VERIFY: 120/120 Photon Energy & 30 Torrent Stacks <<<")
                    current_state = 'START'
                    state_start_time = time.time()
                    cycle_count = 0
                    # Reset ALL cooldowns to READY state using negative values
                    current_time = time.time()
                    for skill in last_cast:
                        last_cast[skill] = -999  # Negative = ready immediately
                    last_auto_attack = 0
                    last_off_cooldown_check = 0
                    last_unpause_time = time.time()
                    script_start_time = time.time()
                    print(">>> ALL SKILLS READY - ULTIMATE, Z, X CAN BE USED IMMEDIATELY <<<")
                    print_cooldown_status()
                else:
                    print(">>> PAUSED <<<")
                    print_cooldown_status()
                time.sleep(0.5)
                
            last_key_check = current_time
        
        # Execute rotation if not paused
        if not paused:
            execute_rotation()
        else:
            time.sleep(0.01)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nStopped by user")
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()