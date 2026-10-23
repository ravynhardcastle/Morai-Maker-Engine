// modified from https://godotshaders.com/shader/2d-drop-shadow/

shader_type canvas_item;

uniform vec4 shadow_color : source_color;
// Currently pixels always in application size, so zooming in further wouldn't increase the size of the dropdown
// but changing that would also be relatively trivial
uniform vec2 offset_in_pixels;
uniform sampler2D caster_texture : filter_nearest;
uniform sampler2D SCREEN_TEXTURE : hint_screen_texture, filter_linear_mipmap;

void fragment() {
	
	// Read screen texture
	vec4 current_color = textureLod(SCREEN_TEXTURE, SCREEN_UV, 0.0);
	
	// Read texture that is grabbed from shadow viewport, so it can cull objects we don't want to shadow
	float caster = textureLod(caster_texture, SCREEN_UV - offset_in_pixels * SCREEN_PIXEL_SIZE, 0.0).a;
		
	// Check if not transparent (i.e., not culled)
	if (caster > 0.0) {
		// If so set it to our shadow color
		current_color = shadow_color;	
	}
	
	COLOR = current_color;
}